import concurrent.futures
from datetime import datetime, timezone
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_service import redis_service
from app.db.session import SessionLocal
from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.user import User
from app.providers.github.auth import GitHubAppAuthService
from app.services.github_installation_service import GitHubInstallationService

logger = logging.getLogger("sutra.github_sync_worker")

SYNC_QUEUE_KEY = "github:sync_jobs"
DEBOUNCE_KEY_PREFIX = "github:sync_lock:"
STATUS_KEY_PREFIX = "github:sync_status:"
DEBOUNCE_SECONDS = 300  # 5 minutes debounce


def get_debounce_key(installation_id: int) -> str:
    return f"{DEBOUNCE_KEY_PREFIX}{installation_id}"


def get_status_key(installation_id: int) -> str:
    return f"{STATUS_KEY_PREFIX}{installation_id}"


def check_sync_debounce(installation_id: int) -> Tuple[bool, int]:
    """
    Check if an installation is within the 5-minute debounce cooldown window.
    Returns (is_debounced, cooldown_remaining_seconds).
    """
    key = get_debounce_key(installation_id)
    try:
        ttl = redis_service.ttl(key)
        if ttl > 0:
            return True, ttl
    except Exception as e:
        logger.debug(f"Redis unavailable while checking debounce for installation {installation_id}: {e}")
    return False, 0


def set_sync_debounce(installation_id: int, ttl: int = DEBOUNCE_SECONDS) -> None:
    """
    Set the 5-minute debounce lock for an installation.
    """
    key = get_debounce_key(installation_id)
    try:
        redis_service.set(key, "1", ex=ttl)
    except Exception as e:
        logger.debug(f"Redis unavailable while setting debounce for installation {installation_id}: {e}")


def get_installation_sync_status(installation_id: int) -> Dict[str, Any]:
    """
    Retrieve current sync status for an installation from Redis.
    """
    key = get_status_key(installation_id)
    try:
        data = redis_service.get(key)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "status": "idle",
        "last_synced_at": None,
    }


def set_installation_sync_status(installation_id: int, status_data: Dict[str, Any]) -> None:
    """
    Save sync status for an installation to Redis with 24-hour expiration.
    """
    key = get_status_key(installation_id)
    try:
        redis_service.set(key, status_data, ex=86400)
    except Exception as e:
        logger.debug(f"Redis unavailable while setting sync status for installation {installation_id}: {e}")


class GitHubSyncWorker:
    """
    Background worker and concurrency controller for GitHub synchronization.
    Features:
    - Bounded worker concurrency (~3-5 workers per installation)
    - Repository failure isolation (one failing repo does not abort others)
    - Staleness guard (1 hour default for issue/PR backfill)
    - Redis queue integration (github:sync_jobs)
    - Installation-level 5-minute debounce
    """

    MAX_CONCURRENCY = 4  # 3-5 concurrent repos per installation

    @classmethod
    def enqueue_job(
        cls,
        installation_id: int,
        user_id: str,
        force: bool = False,
    ) -> bool:
        """
        Push a sync job to the durable Redis queue.
        Also spawns a detached background thread runner to ensure immediate
        execution without blocking the caller HTTP request.
        """
        payload = {
            "installation_id": installation_id,
            "user_id": user_id,
            "force": force,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update status in Redis
        set_installation_sync_status(
            installation_id,
            {
                "status": "in_progress",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "force": force,
            },
        )

        queued_in_redis = False
        try:
            client = redis_service.get_client()
            client.lpush(SYNC_QUEUE_KEY, json.dumps(payload))
            queued_in_redis = True
        except Exception as e:
            logger.warning(f"Could not push job to Redis queue: {e}")

        # Always trigger background execution immediately
        t = threading.Thread(
            target=cls._run_job_safe,
            args=(installation_id, user_id, force),
            daemon=True,
        )
        t.start()
        return queued_in_redis

    @classmethod
    def process_pending(cls, limit: int = 5) -> int:
        """
        Durable queue consumer: pops and executes pending sync jobs from Redis.
        Called by sutra_worker.py or standalone workers.
        """
        processed = 0
        try:
            client = redis_service.get_client()
            for _ in range(limit):
                raw = client.rpop(SYNC_QUEUE_KEY)
                if not raw:
                    break
                try:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    cls.run_installation_sync(
                        installation_id=int(data["installation_id"]),
                        user_id=str(data["user_id"]),
                        force=bool(data.get("force", False)),
                    )
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to process queued sync job {raw}: {e}", exc_info=True)
        except Exception as e:
            logger.debug(f"Redis unavailable for sync worker process_pending: {e}")
        return processed

    @classmethod
    def _run_job_safe(cls, installation_id: int, user_id: str, force: bool) -> None:
        try:
            cls.run_installation_sync(installation_id, user_id, force)
        except Exception as e:
            logger.error(f"Background sync job failed for installation {installation_id}: {e}", exc_info=True)

    @classmethod
    def _sync_single_repo(
        cls,
        repo_id: str,
        installation_id: int,
        force: bool,
        auth_service: GitHubAppAuthService,
        db: Optional[Session] = None,
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Backfill issues & PRs for a single repository in an isolated session.
        Returns (repo_id, success, error_message).
        """
        def _execute(session: Session):
            repo = session.get(Repository, repo_id)
            if not repo:
                return repo_id, False, "Repository not found"

            service = GitHubInstallationService(auth_service)
            try:
                service.sync_repository_engineering_objects(
                    db=session,
                    repository=repo,
                    installation_id=installation_id,
                    force=force,
                )
                return repo_id, True, None
            except Exception as e:
                logger.warning(f"Repository backfill failed for {repo.name} ({repo_id}): {e}")
                return repo_id, False, str(e)

        if db is not None:
            return _execute(db)
        with SessionLocal() as session:
            return _execute(session)

    @classmethod
    def run_installation_sync(
        cls,
        installation_id: int,
        user_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform installation repository listing and bounded concurrent backfill.
        """
        from app.api.integrations import _build_auth_service

        auth_service = _build_auth_service()
        service = GitHubInstallationService(auth_service)

        synced_repos: List[Repository] = []
        with SessionLocal() as db:
            user = db.get(User, user_id)
            installation = db.scalar(
                select(GitHubInstallation).where(
                    GitHubInstallation.github_installation_id == installation_id
                )
            )
            if not user or not installation:
                logger.warning(
                    f"Cannot run sync: user {user_id} or installation {installation_id} not found"
                )
                set_installation_sync_status(
                    installation_id,
                    {
                        "status": "partial_failure",
                        "error": "User or installation record not found",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                return {"status": "failed", "error": "Not found"}

            # 1. Sync repository listing (fast DB upsert)
            try:
                synced_repos = service.sync_repos_for_user(
                    db=db,
                    user=user,
                    installation=installation,
                )
            except Exception as e:
                logger.error(f"Failed to list/sync repositories for installation {installation_id}: {e}")
                set_installation_sync_status(
                    installation_id,
                    {
                        "status": "partial_failure",
                        "error": str(e),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                return {"status": "failed", "error": str(e)}

        # 2. Bounded concurrent backfill across repositories (3-5 max workers)
        repo_ids = [r.id for r in synced_repos]
        failed_repos: List[str] = []
        succeeded_count = 0

        if repo_ids:
            with concurrent.futures.ThreadPoolExecutor(max_workers=cls.MAX_CONCURRENCY) as executor:
                future_to_repo = {
                    executor.submit(
                        cls._sync_single_repo,
                        rid,
                        installation_id,
                        force,
                        auth_service,
                    ): rid
                    for rid in repo_ids
                }

                for future in concurrent.futures.as_completed(future_to_repo):
                    rid = future_to_repo[future]
                    try:
                        _, success, err = future.result()
                        if success:
                            succeeded_count += 1
                        else:
                            failed_repos.append(rid)
                    except Exception as exc:
                        logger.error(f"Unhandled thread error for repo {rid}: {exc}")
                        failed_repos.append(rid)

        # 3. Finalize status
        final_status = "completed" if not failed_repos else "partial_failure"
        now_iso = datetime.now(timezone.utc).isoformat()
        status_payload = {
            "status": final_status,
            "last_synced_at": now_iso,
            "synced_count": succeeded_count,
            "failed_count": len(failed_repos),
            "failed_repos": failed_repos,
            "completed_at": now_iso,
        }
        set_installation_sync_status(installation_id, status_payload)

        logger.info(
            f"GitHub sync finished for installation {installation_id}: status={final_status}, "
            f"succeeded={succeeded_count}, failed={len(failed_repos)}"
        )
        return status_payload
