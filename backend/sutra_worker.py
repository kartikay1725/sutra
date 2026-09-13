import argparse
import logging
import signal
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.git_push_event_processor import (
    GitPushEventProcessor,
)


logger = logging.getLogger(
    "sutra.worker"
)


class Worker:

    def __init__(
        self,
        interval: float,
        batch_size: int,
        stale_timeout: int,
    ):
        self.interval = interval
        self.batch_size = batch_size
        self.stale_timeout = stale_timeout
        self.running = True

    def stop(
        self,
        signum=None,
        frame=None,
    ) -> None:

        if self.running:
            logger.info(
                "Shutdown signal received."
            )

        self.running = False

    def process_once(self) -> int:

        db = SessionLocal()
        total_processed = 0

        try:

            processor = GitPushEventProcessor(
                db
            )

            events = processor.process_pending(
                limit=self.batch_size,
                stale_timeout_seconds=(
                    self.stale_timeout
                ),
            )

            total_processed += len(events)

        finally:
            db.close()

        try:
            from app.services.github_sync_worker import GitHubSyncWorker

            sync_count = GitHubSyncWorker.process_pending(limit=5)
            total_processed += sync_count
        except Exception as e:
            logger.debug(f"GitHubSyncWorker cycle error: {e}")

        return total_processed

    def run(self) -> None:

        logger.info(
            "SUTRA worker started "
            "interval=%ss batch_size=%s "
            "stale_timeout=%ss",
            self.interval,
            self.batch_size,
            self.stale_timeout,
        )

        while self.running:

            started = time.monotonic()

            try:

                count = self.process_once()

                if count:
                    logger.info(
                        "Processed %s event(s).",
                        count,
                    )

            except Exception:

                logger.exception(
                    "Worker cycle failed."
                )

            elapsed = (
                time.monotonic()
                - started
            )

            remaining = max(
                0.0,
                self.interval - elapsed,
            )

            end = (
                time.monotonic()
                + remaining
            )

            while (
                self.running
                and time.monotonic() < end
            ):
                time.sleep(
                    min(
                        0.25,
                        end - time.monotonic(),
                    )
                )

        logger.info(
            "SUTRA worker stopped."
        )


def configure_logging() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "[%(name)s] "
            "%(message)s"
        ),
    )


def process_once(
    limit: int,
    stale_timeout: int,
) -> int:

    db = SessionLocal()
    total = 0

    try:

        processor = GitPushEventProcessor(
            db
        )

        events = processor.process_pending(
            limit=limit,
            stale_timeout_seconds=(
                stale_timeout
            ),
        )

        total += len(events)

    finally:
        db.close()

    try:
        from app.services.github_sync_worker import GitHubSyncWorker

        total += GitHubSyncWorker.process_pending(limit=5)
    except Exception:
        pass

    return total


def main() -> None:

    parser = argparse.ArgumentParser(
        description="SUTRA Git push event worker"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Process pending events once "
            "and exit."
        ),
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=getattr(
            settings,
            "worker_interval_seconds",
            2.0,
        ),
        help=(
            "Polling interval in seconds."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=getattr(
            settings,
            "worker_batch_size",
            100,
        ),
        help=(
            "Maximum events processed "
            "per cycle."
        ),
    )

    parser.add_argument(
        "--stale-timeout",
        type=int,
        default=getattr(
            settings,
            "worker_stale_timeout_seconds",
            300,
        ),
        help=(
            "Seconds before a processing "
            "event is considered stale."
        ),
    )

    args = parser.parse_args()

    if args.batch_size < 1:
        raise SystemExit(
            "--batch-size must be positive"
        )

    if args.interval <= 0:
        raise SystemExit(
            "--interval must be positive"
        )

    if args.stale_timeout <= 0:
        raise SystemExit(
            "--stale-timeout must be positive"
        )

    configure_logging()

    if args.once:

        count = process_once(
            args.batch_size,
            args.stale_timeout,
        )

        logger.info(
            "SUTRA worker processed "
            "%s event(s).",
            count,
        )

        return

    worker = Worker(
        interval=args.interval,
        batch_size=args.batch_size,
        stale_timeout=args.stale_timeout,
    )

    signal.signal(
        signal.SIGINT,
        worker.stop,
    )

    if hasattr(
        signal,
        "SIGTERM",
    ):
        signal.signal(
            signal.SIGTERM,
            worker.stop,
        )

    worker.run()


if __name__ == "__main__":
    main()