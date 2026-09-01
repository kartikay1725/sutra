from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Dict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.change_event import ChangeEvent
from app.models.ci_job import CIJob
from app.services.ci_sandbox import CISandbox


class CIRunner:
    """
    Secure isolated CI Runner boundary.

    Enforces strict environment isolation, argument list execution (shell=False),
    bounded output logs, workspace cleanup, and secret stripping.
    """

    MAX_LOG_BYTES = 100 * 1024  # 100 KB max log size
    TIMEOUT_SECONDS = 30  # 30 second execution limit

    def __init__(self, db: Session):
        self.db = db

    def _build_isolated_env(self, job: CIJob) -> Dict[str, str]:
        # Explicit whitelist of environment variables - NEVER pass host secrets
        allowed_keys = {"PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP"}
        isolated_env = {k: v for k, v in os.environ.items() if k in allowed_keys}
        isolated_env.update({
            "CI": "true",
            "SUTRA_CI_JOB_ID": job.id,
            "SUTRA_CI_COMMIT_SHA": job.commit_sha,
            "SUTRA_CI_TARGET_BRANCH": job.target_branch,
            "PYTHONUNBUFFERED": "1",
        })
        return isolated_env

    def execute_job(self, job_id: str, worker_id: str) -> CIJob:
        job = self.db.scalar(
            select(CIJob).where(CIJob.id == job_id).with_for_update()
        )
        if not job or job.status != CIJob.STATUS_QUEUED:
            return job

        now = datetime.now(timezone.utc)
        job.status = CIJob.STATUS_RUNNING
        job.worker_id = worker_id
        job.started_at = now
        job.lease_expires_at = datetime.fromtimestamp(now.timestamp() + 300, tz=timezone.utc)
        self.db.flush()

        try:
            sandbox = CISandbox()
            res = sandbox.run_container_verification(
                job_id=job.id,
                commit_sha=job.commit_sha,
                target_branch=job.target_branch,
            )

            job.output_log = res["output_log"]
            job.exit_code = res["exit_code"]
            job.completed_at = datetime.now(timezone.utc)

            if res["timed_out"]:
                job.status = CIJob.STATUS_TIMED_OUT
                job.failure_reason = f"CI Job container execution timed out after {sandbox.TIMEOUT_SECONDS}s"
                event_type = "ci.job_timed_out"
            elif res["exit_code"] == 0:
                job.status = CIJob.STATUS_PASSED
                event_type = "ci.job_passed"
            else:
                job.status = CIJob.STATUS_FAILED
                job.failure_reason = f"Verification container failed with exit code {res['exit_code']}"
                event_type = "ci.job_failed"

        except Exception as e:
            job.status = CIJob.STATUS_FAILED
            job.exit_code = -1
            job.failure_reason = f"Sandbox execution error: {str(e)}"
            job.completed_at = datetime.now(timezone.utc)
            event_type = "ci.job_failed"

        event = ChangeEvent(
            id=str(uuid4()),
            change_id=job.change_id,
            event_type=event_type,
            actor_id=worker_id,
            metadata_json=f'{{"job_id": "{job.id}", "commit_sha": "{job.commit_sha}", "status": "{job.status}"}}',
        )
        self.db.add(event)
        self.db.flush()

        # Check if there is another queued job for this repository and run it
        next_job = self.db.scalar(
            select(CIJob)
            .where(
                CIJob.repository_id == job.repository_id,
                CIJob.status == CIJob.STATUS_QUEUED,
            )
            .order_by(CIJob.created_at.asc())
        )
        if next_job:
            try:
                self.execute_job(next_job.id, worker_id)
            except Exception:
                pass

        return job
