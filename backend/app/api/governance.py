from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.governance_policy import GovernancePolicy
from app.models.organization import Organization, OrganizationMember
from app.models.user import User


router = APIRouter(prefix="/v1/organizations", tags=["governance"])


class GovernancePolicyPayload(BaseModel):
    enforce_branch_protection: bool = True
    minimum_pr_approvals: int = Field(default=1, ge=0, le=20)
    restrict_public_repositories: bool = False
    require_signed_commits: bool = False


class GovernancePolicyResponse(GovernancePolicyPayload):
    organization_id: str

    model_config = ConfigDict(from_attributes=True)


def _get_org(db: Session, org_id: str) -> Organization:
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _member(db: Session, org_id: str, user_id: str) -> OrganizationMember | None:
    return (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .first()
    )


def _require_admin(db: Session, org_id: str, user: User) -> OrganizationMember:
    member = _member(db, org_id, user.id)
    if not member:
        raise HTTPException(status_code=403, detail="You are not a member of this organization")
    if member.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Organization admin access required")
    return member


def _default_policy(org_id: str) -> GovernancePolicy:
    return GovernancePolicy(
        organization_id=org_id,
        enforce_branch_protection=True,
        minimum_pr_approvals=1,
        restrict_public_repositories=False,
        require_signed_commits=False,
    )


@router.get("/{org_id}/policies", response_model=GovernancePolicyResponse)
def get_governance_policies(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_org(db, org_id)
    member = _member(db, org_id, current_user.id)
    if not member:
        raise HTTPException(status_code=403, detail="Organization membership required")

    policy = db.get(GovernancePolicy, org_id)
    if policy is None:
        policy = _default_policy(org_id)
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


@router.put("/{org_id}/policies", response_model=GovernancePolicyResponse)
def update_governance_policies(
    org_id: str,
    payload: GovernancePolicyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_org(db, org_id)
    _require_admin(db, org_id, current_user)

    policy = db.get(GovernancePolicy, org_id)
    if policy is None:
        policy = GovernancePolicy(organization_id=org_id)
        db.add(policy)

    policy.enforce_branch_protection = payload.enforce_branch_protection
    policy.minimum_pr_approvals = payload.minimum_pr_approvals
    policy.restrict_public_repositories = payload.restrict_public_repositories
    policy.require_signed_commits = payload.require_signed_commits

    db.commit()
    db.refresh(policy)
    return policy
