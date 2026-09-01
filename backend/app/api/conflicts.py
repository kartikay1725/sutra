from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.change import Change
from app.models.repository import Repository
from app.models.user import User
from app.services.conflict_service import ConflictService


router = APIRouter(
    prefix="/v1/changes",
    tags=["conflicts"],
)


class ConflictResponse(BaseModel):
    change_id: str
    level: str
    reason: str
    paths: list[str]
    related_change_ids: list[str]


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
    "/{change_id}/conflicts",
    response_model=ConflictResponse,
)
def analyze_conflicts(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = get_owned_change(
        change_id,
        current_user,
        db,
    )

    result = ConflictService(db).analyze(change)

    return ConflictResponse(
        change_id=change.id,
        level=result.level,
        reason=result.reason,
        paths=result.paths,
        related_change_ids=result.related_change_ids,
    )


@router.get(
    "/{change_id}/conflicts/{other_change_id}",
    response_model=ConflictResponse,
)
def compare_conflicts(
    change_id: str,
    other_change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = get_owned_change(
        change_id,
        current_user,
        db,
    )

    other_change = get_owned_change(
        other_change_id,
        current_user,
        db,
    )

    if change.repository_id != other_change.repository_id:
        raise HTTPException(
            status_code=400,
            detail="Changes must belong to the same repository",
        )

    result = ConflictService(db).compare_changes(
        change,
        other_change,
    )

    return ConflictResponse(
        change_id=change.id,
        level=result.level,
        reason=result.reason,
        paths=result.paths,
        related_change_ids=[other_change.id],
    )
