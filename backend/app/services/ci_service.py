from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.ci_runner import CIRunner


class CIService:
    def __init__(self, db: Session):
        self.db = db

    def _authorize_user(
        self,
        actor_id: str,
        repository: Repository,
    ) -> None:
        if repository.owner_id == actor_id:
            return

        actor = self.db.scalar(
            select(Actor).where(
                Actor.id == actor_id
            )
        )

        if actor is None:
            user = self.db.scalar(
                select(User).where(
                    User.id == actor_id
                )
            )
            if not user:
                raise PermissionError(
                    "User or actor not found"
                )

            actor = Actor(
                id=actor_id,
                owner_id=actor_id,
                type="human",
                name=user.username,
                capabilities=(
                    '["repository.read", '
                    '"repository.write", '
                    '"change.create"]'
                ),
            )
            self.db.add(actor)
            self.db.flush()

        if repository.visibility == "private":
            auth_res = AuthorizationService.check(
                actor,
                repository,
                AuthorizationService.READ,
                db=self.db,
            )
            if not auth_res.allowed:
                raise PermissionError(
                    "User does not have access to this private repository"
                )

    def create_job(
        self,
        pull_request_id: str,
        actor_id: str,
        trigger: str = "pull_request",
    ) -> CIJob:
        pr = self.db.scalar(
            select(PullRequest).where(
                PullRequest.id
                == pull_request_id
            )
        )

        if not pr:
            raise ValueError(
                "PullRequest not found"
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )

        if not repo:
            raise ValueError(
                "Repository not found or deleted"
            )

        self._authorize_user(
            actor_id,
            repo,
        )

        change = self.db.scalar(
            select(Change).where(
                Change.id
                == pr.source_change_id
            )
        )

        if (
            not change
            or not change.resulting_commit
        ):
            raise ValueError(
                "Source Change or resulting commit not found"
            )

        job = CIJob(
            id=str(uuid4()),
            pull_request_id=pr.id,
            repository_id=repo.id,
            change_id=change.id,
            commit_sha=change.resulting_commit,
            target_branch=pr.target_branch,
            status=CIJob.STATUS_QUEUED,
            trigger=trigger,
            runner_type="isolated_process",
        )

        self.db.add(job)

        event = ChangeEvent(
            id=str(uuid4()),
            change_id=change.id,
            event_type="ci.job_created",
            actor_id=actor_id,
            metadata_json=(
                f'{{"job_id": "{job.id}", '
                f'"commit_sha": "{job.commit_sha}"}}'
            ),
        )

        self.db.add(event)
        self.db.flush()

        return job

    def get_job(
        self,
        job_id: str,
        actor_id: str,
    ) -> CIJob:
        job = self.db.scalar(
            select(CIJob).where(
                CIJob.id == job_id
            )
        )

        if not job:
            raise ValueError(
                "CI Job not found"
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id
                == job.repository_id
            )
        )

        if repo:
            self._authorize_user(
                actor_id,
                repo,
            )

        return job

    def list_jobs_for_pr(
        self,
        pull_request_id: str,
        actor_id: str,
    ) -> List[CIJob]:
        pr = self.db.scalar(
            select(PullRequest).where(
                PullRequest.id
                == pull_request_id
            )
        )

        if not pr:
            raise ValueError(
                "PullRequest not found"
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id
            )
        )

        if repo:
            self._authorize_user(
                actor_id,
                repo,
            )

        return self.db.scalars(
            select(CIJob)
            .where(
                CIJob.pull_request_id
                == pull_request_id
            )
            .order_by(
                CIJob.created_at.desc()
            )
        ).all()

    def cancel_job(
        self,
        job_id: str,
        actor_id: str,
    ) -> CIJob:
        job = self.db.scalar(
            select(CIJob)
            .where(
                CIJob.id == job_id
            )
            .with_for_update()
        )

        if not job:
            raise ValueError(
                "CI Job not found"
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id
                == job.repository_id
            )
        )

        if repo:
            self._authorize_user(
                actor_id,
                repo,
            )

        if job.status in {
            CIJob.STATUS_QUEUED,
            CIJob.STATUS_RUNNING,
        }:
            job.status = (
                CIJob.STATUS_CANCELLED
            )
            job.cancelled_at = (
                datetime.now(timezone.utc)
            )
            job.completed_at = (
                datetime.now(timezone.utc)
            )

            event = ChangeEvent(
                id=str(uuid4()),
                change_id=job.change_id,
                event_type="ci.job_cancelled",
                actor_id=actor_id,
                metadata_json=(
                    f'{{"job_id": "{job.id}"}}'
                ),
            )

            self.db.add(event)
            self.db.flush()

        return job

    def run_execution(
        self,
        job_id: str,
        worker_id: str,
    ) -> CIJob:
        runner = CIRunner(
            self.db
        )

        return runner.execute_job(
            job_id,
            worker_id,
        )