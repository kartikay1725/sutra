from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.repository import Repository
from app.models.branch_protection_rule import BranchProtectionRule
from app.services.authorization_service import AuthorizationService
from app.services.branch_protection_service import BranchProtectionService


router = APIRouter(
    tags=["branch-protection"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
SAFE_BRANCH_PATTERN = r"^[a-zA-Z0-9_\-/*.]+$"


def _resolve_repository(repository_id: str, db: Session) -> Repository:
    repo = None
    if re.match(UUID_PATTERN, repository_id):
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.deleted_at.is_(None),
        ).first()
    if repo is None:
        repo = db.query(Repository).filter(
            (Repository.slug == repository_id.lower()) | (Repository.name == repository_id),
            Repository.deleted_at.is_(None),
        ).first()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )
    return repo


class BranchProtectionCreateRequest(BaseModel):
    branch_pattern: str = Field(min_length=1, max_length=255, pattern=SAFE_BRANCH_PATTERN)
    enabled: bool = True
    required_approvals: int = Field(default=1, ge=0)
    require_change_review: bool = True
    require_clean_conflict: bool = True
    require_resolved_threads: bool = True
    require_agent_review: bool = False
    require_no_blocking_agent_findings: bool = False
    allow_author_self_approval: bool = False
    require_ci_passed: bool = False


class BranchProtectionUpdateRequest(BaseModel):
    branch_pattern: str | None = Field(default=None, max_length=255, pattern=SAFE_BRANCH_PATTERN)
    enabled: bool | None = None
    required_approvals: int | None = Field(default=None, ge=0)
    require_change_review: bool | None = None
    require_clean_conflict: bool | None = None
    require_resolved_threads: bool | None = None
    require_agent_review: bool | None = None
    require_no_blocking_agent_findings: bool | None = None
    allow_author_self_approval: bool | None = None
    require_ci_passed: bool | None = None


class BranchProtectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    branch_pattern: str
    enabled: bool
    required_approvals: int
    require_change_review: bool
    require_clean_conflict: bool
    require_resolved_threads: bool
    require_agent_review: bool
    require_no_blocking_agent_findings: bool
    allow_author_self_approval: bool
    require_ci_passed: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@router.get(
    "/v1/repositories/{repository_id}/branch-protection",
    response_model=list[BranchProtectionResponse],
)
def list_branch_protection_rules(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(repository_id, db)

    svc = BranchProtectionService(db)
    user_actor = svc._get_user_actor(current_user.id)
    if (
        repository.owner_id != current_user.id
        and repository.visibility == "private"
        and not getattr(current_user, "is_superuser", False)
    ):
        auth_res = AuthorizationService.check(
            user_actor,
            repository,
            AuthorizationService.READ,
            db=db,
        )
        if not auth_res.allowed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

    return db.query(BranchProtectionRule).filter(
        BranchProtectionRule.repository_id == repository.id,
    ).order_by(BranchProtectionRule.branch_pattern.asc()).all()


@router.post(
    "/v1/repositories/{repository_id}/branch-protection",
    response_model=BranchProtectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch_protection_rule(
    repository_id: str,
    payload: BranchProtectionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(repository_id, db)

    svc = BranchProtectionService(db)
    try:
        rule = svc.create_rule(
            repository_id=repository.id,
            actor_user_id=current_user.id,
            branch_pattern=payload.branch_pattern,
            enabled=payload.enabled,
            required_approvals=payload.required_approvals,
            require_change_review=payload.require_change_review,
            require_clean_conflict=payload.require_clean_conflict,
            require_resolved_threads=payload.require_resolved_threads,
            require_agent_review=payload.require_agent_review,
            require_no_blocking_agent_findings=payload.require_no_blocking_agent_findings,
            allow_author_self_approval=payload.allow_author_self_approval,
            require_ci_passed=payload.require_ci_passed,
        )
        db.commit()
        return rule
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.patch(
    "/v1/repositories/{repository_id}/branch-protection/{rule_id}",
    response_model=BranchProtectionResponse,
)
def update_branch_protection_rule(
    repository_id: str,
    rule_id: str,
    payload: BranchProtectionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(repository_id, db)
    if not re.match(UUID_PATTERN, rule_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository or Rule not found",
        )

    svc = BranchProtectionService(db)
    updates = payload.model_dump(exclude_unset=True)
    try:
        rule = svc.update_rule(
            rule_id=rule_id,
            actor_user_id=current_user.id,
            **updates,
        )
        db.commit()
        return rule
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.delete(
    "/v1/repositories/{repository_id}/branch-protection/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_branch_protection_rule(
    repository_id: str,
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(repository_id, db)
    if not re.match(UUID_PATTERN, rule_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository or Rule not found",
        )

    svc = BranchProtectionService(db)
    try:
        svc.delete_rule(rule_id=rule_id, actor_user_id=current_user.id)
        db.commit()
        return None
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
