import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.providers.base import RepositoryProvider
from app.services.authorization_service import AuthorizationService
from app.services.ci_runner import CIRunner

logger = logging.getLogger("sutra.services.ci")


class CIService:
    def __init__(self, db: Session, provider: Optional[RepositoryProvider] = None):
        self.db = db
        self.provider = provider

    def _get_provider(self, repository: Repository) -> Optional[RepositoryProvider]:
        if self.provider is not None:
            return self.provider
        if repository.provider_type == "github" and repository.provider_owner:
            if settings.github_app_id and settings.github_private_key_pem:
                try:
                    from app.providers.github.auth import GitHubAppAuthService
                    from app.providers.github.repository import GitHubRepositoryProvider
                    auth_service = GitHubAppAuthService(
                        app_id=settings.github_app_id,
                        private_key_pem=settings.github_private_key_pem,
                        base_url=settings.github_api_base_url,
                    )
                    return GitHubRepositoryProvider(
                        auth_service=auth_service,
                        base_url=settings.github_api_base_url,
                    )
                except Exception:
                    return None
        return None

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

        runner_type = "github_actions" if repo.provider_type == "github" else "isolated_process"
        job = CIJob(
            id=str(uuid4()),
            pull_request_id=pr.id,
            repository_id=repo.id,
            change_id=change.id,
            commit_sha=change.resulting_commit,
            target_branch=pr.target_branch,
            status=CIJob.STATUS_QUEUED,
            trigger=trigger,
            runner_type=runner_type,
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

        if repo and repo.provider_type == "github":
            self.sync_github_checks(pull_request_id, actor_id)

        raw_jobs = self.db.scalars(
            select(CIJob)
            .where(
                CIJob.pull_request_id
                == pull_request_id
            )
            .order_by(
                CIJob.created_at.desc()
            )
        ).all()

        if repo and repo.provider_type == "github":
            return [
                j for j in raw_jobs
                if not (j.runner_type == "isolated_process" and j.failure_reason and "Docker container runtime is unavailable" in j.failure_reason)
                and not (j.runner_type == "github_actions" and j.trigger == "pull_request" and not j.started_at and not j.completed_at)
            ]

        return raw_jobs

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

    def sync_github_checks(
        self,
        pull_request_id: str,
        actor_id: Optional[str] = None,
    ) -> List[CIJob]:
        pr = self.db.scalar(
            select(PullRequest).where(
                PullRequest.id == pull_request_id
            )
        )
        if not pr:
            raise ValueError("PullRequest not found")

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo or repo.provider_type != "github":
            return []

        if actor_id:
            self._authorize_user(actor_id, repo)

        head_sha = pr.source_commit
        if not head_sha:
            change = self.db.scalar(
                select(Change).where(Change.id == pr.source_change_id)
            )
            head_sha = change.resulting_commit if change else None

        if not head_sha:
            return []

        provider = self._get_provider(repo)
        if not provider:
            return []

        synced_jobs = []
        try:
            owner = repo.provider_owner or "kartikay1725"
            gh_check_runs = provider.list_check_runs(owner, repo.name, head_sha)
            sorted_check_runs = sorted(gh_check_runs, key=lambda c: c.get("id", 0))
            for cr in sorted_check_runs:
                check_name = cr.get("name") or f"check_{cr['id']}"
                job_trigger = check_name[:50]
                existing_job = self.db.scalar(
                    select(CIJob).where(
                        CIJob.pull_request_id == pr.id,
                        CIJob.commit_sha == head_sha,
                        CIJob.trigger == job_trigger,
                    )
                )
                conc = (cr.get("conclusion") or "").lower()
                st = (cr.get("status") or "").lower()
                if conc == "success":
                    j_status = CIJob.STATUS_PASSED
                elif conc in ("failure", "timed_out", "action_required"):
                    j_status = CIJob.STATUS_FAILED
                elif conc in ("cancelled", "skipped", "neutral"):
                    j_status = CIJob.STATUS_CANCELLED if conc == "cancelled" else CIJob.STATUS_PASSED
                elif st in ("in_progress", "running"):
                    j_status = CIJob.STATUS_RUNNING
                else:
                    j_status = CIJob.STATUS_QUEUED

                started_dt = None
                if cr.get("started_at"):
                    try:
                        started_dt = datetime.fromisoformat(cr["started_at"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                completed_dt = None
                if cr.get("completed_at"):
                    try:
                        completed_dt = datetime.fromisoformat(cr["completed_at"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                output_url = cr.get("html_url") or cr.get("details_url")

                if not existing_job:
                    new_job = CIJob(
                        id=str(uuid4()),
                        pull_request_id=pr.id,
                        repository_id=repo.id,
                        change_id=pr.source_change_id,
                        commit_sha=head_sha,
                        target_branch=pr.target_branch,
                        status=j_status,
                        trigger=job_trigger,
                        runner_type="github_actions",
                        output_log=output_url,
                        failure_reason=conc if j_status == CIJob.STATUS_FAILED else None,
                        started_at=started_dt,
                        completed_at=completed_dt,
                    )
                    self.db.add(new_job)
                    synced_jobs.append(new_job)
                else:
                    existing_job.status = j_status
                    existing_job.runner_type = "github_actions"
                    if output_url:
                        existing_job.output_log = output_url
                    if completed_dt:
                        existing_job.completed_at = completed_dt
                    if j_status == CIJob.STATUS_FAILED:
                        existing_job.failure_reason = conc
                    synced_jobs.append(existing_job)
            self.db.flush()
        except Exception as e:
            logger.warning(f"Could not sync GitHub check runs for {head_sha}: {e}")

        return synced_jobs

    def get_pr_checks(
        self,
        pull_request_id: str,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        pr = self.db.scalar(
            select(PullRequest).where(
                PullRequest.id == pull_request_id
            )
        )
        if not pr:
            raise ValueError("PullRequest not found")

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            raise ValueError("Repository not found or deleted")

        if actor_id:
            self._authorize_user(actor_id, repo)

        head_sha = pr.source_commit
        if not head_sha:
            change = self.db.scalar(
                select(Change).where(Change.id == pr.source_change_id)
            )
            head_sha = change.resulting_commit if change else None

        if repo.provider_type == "github":
            # Throttle external GitHub sync so repeated/concurrent calls within 20s don't block
            sync_key = f"github:checks:sync:{pull_request_id}"
            from app.core.redis_service import redis_service
            should_sync = True
            try:
                if redis_service.get(sync_key):
                    should_sync = False
                else:
                    redis_service.set(sync_key, "1", ex=20)
            except Exception:
                pass

            if should_sync:
                try:
                    self.sync_github_checks(pull_request_id, actor_id=actor_id)
                except Exception as exc:
                    logger.warning(f"Failed to sync GitHub checks: {exc}")

        # Query all jobs associated with the PR head commit
        jobs = []
        if head_sha:
            jobs = self.db.scalars(
                select(CIJob).where(
                    CIJob.pull_request_id == pr.id,
                    CIJob.commit_sha == head_sha,
                ).order_by(CIJob.created_at.desc())
            ).all()

        checks_list = []
        has_specific_gh_jobs = any(
            (j.runner_type == "github_actions" or (j.trigger and j.trigger.startswith("github_check_")))
            and j.trigger != "pull_request"
            for j in jobs
        )

        owner = repo.provider_owner or "kartikay1725"
        for j in jobs:
            # If repository is on GitHub, disregard local isolated_process errors caused by missing host Docker
            if repo.provider_type == "github" and j.runner_type == "isolated_process" and j.failure_reason and "Docker container runtime is unavailable" in j.failure_reason:
                continue

            # For GitHub repositories, skip placeholder dispatch jobs (only display actual GitHub check runs)
            if repo.provider_type == "github" and j.runner_type == "github_actions" and j.trigger == "pull_request":
                continue

            is_github = j.runner_type == "github_actions" or (j.trigger and j.trigger.startswith("github_check_"))
            name = j.trigger or "verification"

            # SUTRA normalized status mapping
            if j.status == CIJob.STATUS_PASSED:
                conclusion = "success"
                sutra_state = "passed"
                status_val = "completed"
            elif j.status == CIJob.STATUS_FAILED:
                conclusion = "failure"
                sutra_state = "failed"
                status_val = "completed"
            elif j.status == CIJob.STATUS_CANCELLED:
                conclusion = "cancelled"
                sutra_state = "cancelled"
                status_val = "completed"
            elif j.status == CIJob.STATUS_RUNNING:
                conclusion = None
                sutra_state = "running"
                status_val = "in_progress"
            else:
                conclusion = None
                sutra_state = "pending"
                status_val = "queued"

            output_url = j.output_log if (j.output_log and j.output_log.startswith("http")) else None
            if not output_url and is_github:
                output_url = f"https://github.com/{owner}/{repo.name}/actions"

            checks_list.append({
                "id": j.id,
                "name": name,
                "head_sha": j.commit_sha,
                "status": status_val,
                "conclusion": conclusion,
                "sutra_state": sutra_state,
                "html_url": output_url,
                "details_url": output_url,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "source": "github" if is_github else "sutra",
                "app_name": "GitHub Actions" if is_github else "SUTRA CI",
                "required": True,
            })

        total = len(checks_list)
        passed = sum(1 for c in checks_list if c["sutra_state"] in ("passed", "success"))
        failed = sum(1 for c in checks_list if c["sutra_state"] in ("failed", "failure"))
        running = sum(1 for c in checks_list if c["sutra_state"] in ("running", "in_progress"))
        pending = sum(1 for c in checks_list if c["sutra_state"] in ("pending", "queued"))

        has_ci_file = True
        message = None

        if total == 0:
            overall_status = "none"
            governance_verdict = "NO CI FILE CONFIGURED"
            # Never block a PR from being merged if there is no CI file and CI checks cannot be run
            ready_for_governance = True
            has_ci_file = False
            message = "No CI file found in codebase. Cannot run CI checks. If you want automated checks, please create a .github/workflows/ci.yml file."
        elif failed > 0:
            overall_status = "failed"
            governance_verdict = "BLOCKED BY CI"
            ready_for_governance = False
        elif running > 0 or pending > 0:
            overall_status = "running"
            governance_verdict = "CHECKS IN PROGRESS"
            ready_for_governance = False
        else:
            overall_status = "passed"
            governance_verdict = "READY FOR GOVERNANCE"
            ready_for_governance = True

        return {
            "pull_request_id": pr.id,
            "repository_id": repo.id,
            "head_sha": head_sha or "",
            "overall_status": overall_status,
            "governance_verdict": governance_verdict,
            "ready_for_governance": ready_for_governance,
            "has_ci_file": has_ci_file,
            "message": message,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "running": running,
                "pending": pending,
            },
            "checks": checks_list,
        }