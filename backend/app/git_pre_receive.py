"""Synchronous Git pre-receive policy gate used by bare repository hooks."""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select


ZERO_SHA = "0" * 40


def _git_dir() -> Path:
    value = (
        os.environ.get("SUTRA_REPOSITORY_PATH")
        or os.environ.get("GIT_DIR")
        or os.getcwd()
    )
    return Path(value).resolve()


def _is_ancestor(
    repository_path: Path,
    before: str,
    after: str,
) -> bool:
    result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repository_path),
            "merge-base",
            "--is-ancestor",
            "--",
            before,
            after,
        ],
        capture_output=True,
        check=False,
    )

    return result.returncode == 0


def _parse_updates(
    repository_path: Path,
):
    # Import the dataclass lazily so a system/bootstrap hook does not need
    # to initialize the application settings or database layer.
    from app.services.git_receive_policy_service import RefUpdateProposal

    updates = []

    for raw_line in sys.stdin:
        parts = raw_line.strip().split()

        if len(parts) != 3:
            raise ValueError("Malformed pre-receive ref update")

        old_sha, new_sha, ref = parts

        before = None if old_sha == ZERO_SHA else old_sha
        after = None if new_sha == ZERO_SHA else new_sha

        if before is None and after is not None:
            operation = "create"
            forced = False
        elif before is not None and after is None:
            operation = "delete"
            forced = False
        elif before == after:
            operation = "unchanged"
            forced = False
        else:
            operation = "update"
            forced = not _is_ancestor(
                repository_path,
                before,
                after,
            )

        updates.append(
            RefUpdateProposal(
                before_commit=before,
                after_commit=after,
                ref=ref,
                operation=operation,
                forced=forced,
            )
        )

    return updates


def _repository_storage_key(
    repository_path: Path,
) -> str:
    return repository_path.name


def main() -> int:
    principal_kind = os.environ.get(
        "SUTRA_PRINCIPAL_KIND"
    )

    # System/bootstrap pushes do not require DB-backed agent authorization.
    if principal_kind != "agent":
        return 0

    # Import the DB/application layer only after the Git HTTP process has
    # provided its runtime environment to the hook.
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
    else:
        from app.db.session import SessionLocal

    from app.models.actor import Actor
    from app.models.agent import Agent
    from app.models.repository import Repository
    from app.services.git_receive_policy_service import (
        GitReceivePolicyService,
    )

    repository_id = os.environ.get(
        "SUTRA_REPOSITORY_ID"
    )

    actor_id = os.environ.get(
        "SUTRA_ACTOR_ID"
    )

    if not actor_id:
        print(
            "SUTRA: missing receive-gate actor identity context",
            file=sys.stderr,
        )
        return 1

    repository_path = _git_dir()

    storage_key = _repository_storage_key(
        repository_path
    )

    updates = _parse_updates(
        repository_path
    )

    if not updates:
        return 0

    with SessionLocal() as db:
        repository = None

        if repository_id:
            repository = db.scalar(
                select(Repository).where(
                    Repository.id == repository_id,
                    Repository.deleted_at.is_(None),
                )
            )

        if repository is None and storage_key:
            repository = db.scalar(
                select(Repository).where(
                    Repository.storage_key == storage_key,
                    Repository.deleted_at.is_(None),
                )
            )

        if repository is None:
            print(
                (
                    "SUTRA: repository no longer exists "
                    f"(id={repository_id!r}, "
                    f"storage_key={storage_key!r}, "
                    f"cwd={os.getcwd()!r}, "
                    f"git_dir={str(repository_path)!r})"
                ),
                file=sys.stderr,
            )
            return 1

        actor = db.scalar(
            select(Actor).where(
                Actor.id == actor_id,
                Actor.type == "agent",
            )
        )

        if actor is None:
            print(
                "SUTRA: agent actor identity no longer exists",
                file=sys.stderr,
            )
            return 1

        agent = db.scalar(
            select(Agent).where(
                Agent.id == actor.id,
                Agent.is_active.is_(True),
                Agent.status == "active",
                Agent.owner_id == repository.owner_id,
            )
        )

        if agent is None:
            print(
                (
                    "SUTRA: agent is inactive, revoked, "
                    "or does not own the target repository"
                ),
                file=sys.stderr,
            )
            return 1

        decision = GitReceivePolicyService(
            db
        ).evaluate(
            repository=repository,
            actor=actor,
            updates=updates,
        )

        if decision.decision != "allow":
            print(
                (
                    "SUTRA: push rejected by receive policy: "
                    + decision.reason
                ),
                file=sys.stderr,
            )

            for reason in decision.reasons[1:]:
                print(
                    f"SUTRA: {reason}",
                    file=sys.stderr,
                )

            return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
