from __future__ import annotations

import logging
import threading
import time
import uuid

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.git_push_event_processor import (
    GitPushEventProcessor,
)
from app.services.git_push_event_service import (
    GitPushEventService,
)

logger = logging.getLogger("sutra.git_push_event_worker")


class GitPushEventWorker:
    """
    Durable worker for persisted Git push events.

    PostgreSQL is the durable queue.

    Lifecycle:

        pending/failed
            ↓
        processing
            ↓
        processor
            ├── processed
            └── failed

    A stale processing event can be recovered by a later worker.
    """

    def __init__(
        self,
        *,
        interval_seconds: float | None = None,
        batch_size: int | None = None,
        stale_timeout_seconds: int | None = None,
    ) -> None:

        self.interval_seconds = (
            interval_seconds
            if interval_seconds is not None
            else settings.worker_interval_seconds
        )

        self.batch_size = (
            batch_size
            if batch_size is not None
            else settings.worker_batch_size
        )

        self.stale_timeout_seconds = (
            stale_timeout_seconds
            if stale_timeout_seconds is not None
            else settings.worker_stale_timeout_seconds
        )

        if self.interval_seconds < 0:
            raise ValueError(
                "interval_seconds cannot be negative"
            )

        if self.batch_size < 1:
            raise ValueError(
                "batch_size must be positive"
            )

        if self.batch_size > 1000:
            raise ValueError(
                "batch_size cannot exceed 1000"
            )

        if self.stale_timeout_seconds < 1:
            raise ValueError(
                "stale_timeout_seconds must be positive"
            )

        self._stop_event = threading.Event()

        self.worker_id = (
            GitPushEventService.generate_worker_id()
        )

    # =========================================================
    # SINGLE WORK CYCLE
    # =========================================================

    def run_once(self) -> int:
        """
        Execute one worker cycle.

        Returns the number of events claimed.

        Session creation is deliberately inside the exception
        boundary so database startup failures do not crash the
        worker loop.
        """

        db = None

        try:
            db = SessionLocal()

            events = GitPushEventService(db)

            # -------------------------------------------------
            # STALE RECOVERY
            # -------------------------------------------------

            recovered = events.recover_stale_processing(
                timeout_seconds=self.stale_timeout_seconds
            )

            if recovered:
                db.commit()

                logger.warning(
                    "Recovered %s stale Git push event(s)",
                    recovered,
                )

            # -------------------------------------------------
            # CLAIM
            # -------------------------------------------------

            claimed = events.claim_pending(
                limit=self.batch_size,
                worker_id=self.worker_id,
                lease_seconds=self.stale_timeout_seconds,
            )

            # Make the claim durable before processing.

            db.commit()

            if not claimed:
                return 0

            logger.info(
                "Claimed %s Git push event(s)",
                len(claimed),
            )

            # -------------------------------------------------
            # PROCESS
            # -------------------------------------------------

            processor = GitPushEventProcessor(db)
            processed_count = 0

            for event in claimed:

                event_id = event.id

                try:
                    events.verify_lease(
                        event,
                        self.worker_id,
                    )

                    result = (
                        processor.process_claimed_event(
                            event,
                            worker_id=self.worker_id,
                        )
                    )

                    if result.status == GitPushEventService.STATUS_PROCESSED:
                        processed_count += 1
                        logger.info(
                            "Git push event processed: %s (attempt %s, worker %s)",
                            event_id,
                            result.attempts,
                            self.worker_id,
                        )
                    elif result.status == GitPushEventService.STATUS_DEAD_LETTER:
                        logger.error(
                            "Git push event moved to dead-letter: %s (attempt %s, worker %s, error: %s)",
                            event_id,
                            result.attempts,
                            self.worker_id,
                            result.last_error,
                        )
                    else:
                        logger.warning(
                            "Git push event failed, will retry at %s: %s (attempt %s, worker %s, error: %s)",
                            result.next_attempt_at,
                            event_id,
                            result.attempts,
                            self.worker_id,
                            result.last_error,
                        )

                except Exception:
                    db.rollback()

                    logger.exception(
                        "Unexpected exception while processing "
                        "Git push event %s",
                        event_id,
                    )

            return len(claimed)

        except Exception:

            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback worker session"
                    )

            logger.exception(
                "Git push event worker cycle failed"
            )

            return 0

        finally:

            if db is not None:
                try:
                    db.close()
                except Exception:
                    logger.exception(
                        "Failed to close worker session"
                    )

    # =========================================================
    # CONTINUOUS LOOP
    # =========================================================

    def run_forever(self) -> None:
        """
        Run until stop() is called.
        """

        logger.info(
            "Git push event worker started "
            "(interval=%ss, batch=%s, stale_timeout=%ss)",
            self.interval_seconds,
            self.batch_size,
            self.stale_timeout_seconds,
        )

        while not self._stop_event.is_set():

            started = time.monotonic()

            self.run_once()

            elapsed = time.monotonic() - started

            remaining = max(
                0.0,
                self.interval_seconds - elapsed,
            )

            self._stop_event.wait(
                remaining
            )

        logger.info(
            "Git push event worker stopped"
        )

    # =========================================================
    # SHUTDOWN
    # =========================================================

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()