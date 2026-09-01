import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User

router = APIRouter(prefix="/v1/repositories", tags=["security"])


class SecurityFinding(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    file_path: str
    line_number: int
    status: str
    created_at: datetime


def _parse_metadata(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _can_read_repository(repository: Repository, current_user: User) -> bool:
    # Match the existing repository privacy contract used by review APIs:
    # private repositories are owner-only; public repositories are readable
    # by authenticated users.
    if repository.visibility == "private":
        return repository.owner_id == current_user.id
    return True


@router.get("/{owner}/{repo}/security", response_model=List[SecurityFinding])
def get_security_findings(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(User, Repository.owner_id == User.id)
        .where(
            User.username == owner,
            Repository.name == repo,
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    if not _can_read_repository(repository, current_user):
        raise HTTPException(status_code=404, detail="Repository not found")

    events = db.scalars(
        select(ChangeEvent)
        .join(Change, Change.id == ChangeEvent.change_id)
        .where(
            Change.repository_id == repository.id,
            ChangeEvent.event_type == "agent_review.finding_created",
        )
        .order_by(ChangeEvent.created_at.desc())
    ).all()

    findings: list[SecurityFinding] = []
    seen_comment_ids: set[str] = set()

    for event in events:
        metadata = _parse_metadata(event.metadata_json)
        comment_id = str(metadata.get("comment_id") or event.id)

        # One finding maps to one inline review comment. Ignore duplicate
        # finding events for the same comment if replay/reprocessing occurs.
        if comment_id in seen_comment_ids:
            continue
        seen_comment_ids.add(comment_id)

        comment = db.scalar(
            select(InlineReviewComment).where(
                InlineReviewComment.id == comment_id,
            )
        )

        severity = str(metadata.get("severity") or "medium").lower()
        if severity not in {"critical", "high", "medium", "low"}:
            severity = "medium"

        category = str(metadata.get("category") or "security")
        message = str(metadata.get("message") or "Agent security finding")
        suggested_fix = metadata.get("suggested_fix")

        description = f"[{category}] {message}"
        if suggested_fix:
            description += f" Suggested fix: {suggested_fix}"

        file_path = str(
            metadata.get("path")
            or (comment.path if comment is not None else "")
            or "unknown"
        )

        line_number_value = metadata.get("line_number")
        if line_number_value is None and comment is not None:
            line_number_value = comment.line_number

        try:
            line_number = int(line_number_value or 0)
        except (TypeError, ValueError):
            line_number = 0

        status = (
            comment.status
            if comment is not None
            else str(event.to_status or "active")
        )
        if status not in {"active", "resolved"}:
            status = "active"

        title = f"{category.title()} finding"

        findings.append(
            SecurityFinding(
                id=comment_id,
                severity=severity,
                title=title,
                description=description,
                file_path=file_path,
                line_number=line_number,
                status="open" if status == "active" else "resolved",
                created_at=event.created_at,
            )
        )

    return findings
