from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.change import Change
from app.models.repository import Repository
from app.models.user import User
from app.services.change_policy_service import ChangePolicyService


router = APIRouter(
    prefix="/v1/changes",
    tags=["change-policy"],
)


class PolicyDecisionResponse(BaseModel):
    change_id: str
    decision: str
    reason: str
    reasons: list[str]
    conflict_level: str
    related_change_ids: list[str]
    dependency_count: int
    capabilities: list[str]


def get_owned_change(
    change_id: str,
    current_user: User,
    db: Session,
) -> Change:

    change = db.scalar(
        select(Change)
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
    )

    if change is None:
        raise HTTPException(
            status_code=404,
            detail="Change not found",
        )

    return change


@router.get(
    "/{change_id}/policy",
    response_model=PolicyDecisionResponse,
)
def evaluate_change_policy(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = get_owned_change(
        change_id,
        current_user,
        db,
    )

    result = ChangePolicyService(
        db
    ).evaluate(change)

    return PolicyDecisionResponse(
        change_id=change.id,
        decision=result.decision,
        reason=result.reason,
        reasons=result.reasons,
        conflict_level=result.conflict_level,
        related_change_ids=result.related_change_ids,
        dependency_count=result.dependency_count,
        capabilities=result.capabilities,
    )
