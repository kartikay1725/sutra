from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.organization import Organization, OrganizationMember
from app.models.actor import Actor
from app.models.user import User


router = APIRouter(prefix="/v1/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    display_name: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberResponse(BaseModel):
    organization_id: str
    user_id: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    org_in: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if name is taken globally (by user or org)
    existing_actor = db.query(Actor).filter(Actor.name == org_in.name).first()
    if existing_actor:
        raise HTTPException(status_code=400, detail="Name already taken.")

    # Create actor
    org_id = str(uuid4())
    actor = Actor(
        id=org_id,
        type="organization",
        name=org_in.name,
        capabilities="[]"
    )
    db.add(actor)

    # Create org
    org = Organization(
        id=org_id,
        name=org_in.name,
        display_name=org_in.display_name,
        description=org_in.description
    )
    db.add(org)

    # Create owner member
    member = OrganizationMember(
        organization_id=org_id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_name}", response_model=OrganizationResponse)
def get_organization(org_name: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.name == org_name).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/{org_name}/members", response_model=list[OrganizationMemberResponse])
def get_organization_members(org_name: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.name == org_name).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
    return members
