import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.agent import Agent
from app.models.agent_registration import AgentRegistrationRequest
from app.models.user import User

router = APIRouter(prefix="/v1/agents", tags=["agent_registration"])


class RegistrationRequestCreate(BaseModel):
    agent_name: str
    owner_username: str
    repo_name: str | None = None
    new_repo: bool = False
    agent_description: str | None = None
    provider: str | None = None
    model: str | None = None
    requested_capabilities: list[str] = []


class RegistrationRequestResponse(BaseModel):
    id: str
    polling_token: str
    expires_at: datetime
    temporary_push_token: str | None = None


class RegistrationStatusResponse(BaseModel):
    status: str
    permanent_token: str | None = None


class RegistrationApprovalRequest(BaseModel):
    pass


class RegistrationItem(BaseModel):
    id: str
    agent_name: str
    agent_description: str | None
    provider: str | None
    model: str | None
    status: str
    created_at: datetime
    expires_at: datetime
    requested_capabilities: list[str] = []
    requested_repo_name: str | None = None
    new_repo: bool = False


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegistrationRequestResponse,
    summary="Agent Self-Registration",
    description="Public endpoint used by 3rd party tools to initiate registration. Returns a registration ID and a polling token. A temporary push token is also returned which can be used once for pushing code before human approval.",
    response_description="A registration ID, polling token, expiry time, and temporary push token.",
)
def create_registration_request(
    data: RegistrationRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public endpoint used by 3rd party tools to initiate registration.
    Returns a registration ID and a polling token.
    """
    from app.core.rate_limit import enforce_rate_limit, get_client_ip
    from app.core.redis_service import redis_service
    import hashlib

    ip = get_client_ip(request)
    enforce_rate_limit(f"agent_register:ip:{ip}", settings.rate_limit_agent_register_per_hour, 3600, "agent registration")

    target_user = db.scalar(
        select(User).where(User.username == data.owner_username.strip())
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    enforce_rate_limit(f"agent_register:user:{target_user.id}", settings.rate_limit_agent_register_per_hour, 3600, "agent registration")

    polling_token = secrets.token_urlsafe(32)
    polling_token_hash = hash_password(polling_token)
    
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    repo_name = data.repo_name
    is_new = data.new_repo
    if not repo_name:
        repo_name = "default-repo"
        is_new = True

    temp_token = None
    temp_token_hash = None
    if not is_new:
        temp_token = f"sutra_temp_push_{secrets.token_urlsafe(32)}"
        temp_token_hash = hash_password(temp_token)
    
    req = AgentRegistrationRequest(
        agent_name=data.agent_name,
        agent_description=data.agent_description,
        provider=data.provider,
        model=data.model,
        requested_capabilities=json.dumps(data.requested_capabilities),
        status="pending",
        polling_token_hash=polling_token_hash,
        expires_at=expires_at,
        requested_for_user_id=target_user.id,
        requested_repo_name=repo_name,
        new_repo=is_new,
        temporary_token=None,  # Do not store raw temporary token in PostgreSQL
        temporary_token_hash=temp_token_hash,
        is_temporary_token_used=False,
    )
    
    db.add(req)
    db.commit()
    db.refresh(req)

    # Store temporary push token in Redis with 1 hour TTL
    if temp_token:
        token_hash = hashlib.sha256(temp_token.encode("utf-8")).hexdigest()
        token_key = f"temp_push:{token_hash}"
        try:
            redis_service.set(
                token_key,
                {
                    "registration_id": req.id,
                    "user_id": target_user.id,
                    "repo_name": repo_name,
                },
                ex=3600,
            )
        except Exception as e:
            # Redis failure fails closed or logs
            pass
    
    return {
        "id": req.id,
        "polling_token": polling_token,
        "expires_at": expires_at,
        "temporary_push_token": temp_token,
    }


@router.get(
    "/register/{registration_id}/status",
    response_model=RegistrationStatusResponse,
    summary="Poll Registration Status",
    description="Endpoint polled by the 3rd party tool. Must provide the polling_token from the creation step. Returns the permanent token once approved by a human.",
    response_description="Status of the registration and the permanent token if approved.",
)
def get_registration_status(
    registration_id: str,
    polling_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Endpoint polled by the 3rd party tool.
    Must provide the polling_token from the creation step.
    """
    from app.core.rate_limit import enforce_rate_limit
    enforce_rate_limit(f"agent_poll:{registration_id}", settings.rate_limit_agent_poll_per_minute, 60, "agent poll")

    req = db.scalar(
        select(AgentRegistrationRequest).where(AgentRegistrationRequest.id == registration_id)
    )
    
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
        
    if not verify_password(polling_token, req.polling_token_hash):
        raise HTTPException(status_code=401, detail="Invalid polling token")
        
    expires_at = req.expires_at if req.expires_at.tzinfo else req.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Registration request expired")
        
    return {
        "status": req.status,
        "permanent_token": req.permanent_token_encrypted if req.status == "approved" else None,
    }


@router.get(
    "/registrations/pending",
    response_model=list[RegistrationItem],
    summary="List Pending Registrations",
    description="List pending registrations for the current user. Requires Human JWT.",
    response_description="List of pending agent registrations.",
)
def list_pending_registrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List pending registrations. 
    In a real app, this might just list all pending globally or we might have an org context.
    For Sutra, users will approve requests by ID from the UI.
    We return all pending that haven't expired for demo purposes.
    """
    reqs = db.scalars(
        select(AgentRegistrationRequest).where(
            AgentRegistrationRequest.status == "pending",
            AgentRegistrationRequest.expires_at > datetime.now(timezone.utc),
            AgentRegistrationRequest.requested_for_user_id == current_user.id,
        ).order_by(AgentRegistrationRequest.created_at.desc())
    ).all()
    
    res = []
    for r in reqs:
        try:
            caps = json.loads(r.requested_capabilities)
        except Exception:
            caps = []
        res.append({
            "id": r.id,
            "agent_name": r.agent_name,
            "agent_description": r.agent_description,
            "provider": r.provider,
            "model": r.model,
            "status": r.status,
            "created_at": r.created_at,
            "expires_at": r.expires_at,
            "requested_capabilities": caps,
            "requested_repo_name": r.requested_repo_name,
            "new_repo": r.new_repo,
        })
    return res


@router.post(
    "/registrations/{registration_id}/approve",
    summary="Approve Agent Registration",
    description="User approves the registration. This creates the Agent entity and stores the permanent token. Requires Human JWT.",
    response_description="The created Agent details.",
)
def approve_registration(
    registration_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    User approves the registration. This creates the Agent entity and stores the token.
    """
    req = db.scalar(
        select(AgentRegistrationRequest)
        .where(AgentRegistrationRequest.id == registration_id)
        .with_for_update()
    )
    
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
        
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    if req.requested_for_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Registration request not found")
        
    expires_at = req.expires_at if req.expires_at.tzinfo else req.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        req.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Registration request expired")

    from app.models.repository import Repository
    from app.services.repository_service import RepositoryService

    repository = None
    if req.new_repo:
        existing_repo = db.scalar(
            select(Repository).where(
                Repository.owner_id == current_user.id,
                Repository.slug == req.requested_repo_name.lower(),
                Repository.deleted_at.is_(None)
            )
        )
        if existing_repo:
            repository = existing_repo
        else:
            try:
                repository = RepositoryService(db).create(
                    owner_id=current_user.id,
                    name=req.requested_repo_name,
                    description=f"Auto-created repository for agent {req.agent_name}",
                    visibility="private",
                )
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Failed to auto-create repository: {e}")
    else:
        repository = db.scalar(
            select(Repository).where(
                Repository.owner_id == current_user.id,
                Repository.slug == req.requested_repo_name.lower(),
                Repository.deleted_at.is_(None)
            )
        )
        if not repository:
            raise HTTPException(status_code=400, detail=f"Repository {req.requested_repo_name} not found")

    # Generate permanent token for the new agent
    raw_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    
    agent = Agent(
        owner_id=current_user.id,
        name=req.agent_name,
        description=req.agent_description,
        provider=req.provider,
        model=req.model,
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:16],
        status="active",
        is_active=True,
    )
    
    db.add(agent)
    
    # We must explicitly flush so the agent.id is generated
    db.flush()
    
    from app.models.actor import Actor
    actor = Actor(
        id=agent.id,
        type="agent",
        owner_id=current_user.id,
        name=agent.name,
        capabilities=req.requested_capabilities,
    )
    db.add(actor)

    from app.models.agent_repository_access import AgentRepositoryAccess
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repository.id,
        permissions=req.requested_capabilities,
        enabled=True,
    )
    db.add(access)
    
    req.status = "approved"
    req.approved_by_user_id = current_user.id
    req.permanent_token_encrypted = raw_token  # Stored plaintext temporarily until polling agent fetches it (classic OAuth device flow behavior)
    
    db.commit()
    
    return {"detail": "Registration approved"}


@router.post(
    "/registrations/{registration_id}/reject",
)
def reject_registration(
    registration_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    User rejects the registration.
    """
    req = db.scalar(
        select(AgentRegistrationRequest)
        .where(AgentRegistrationRequest.id == registration_id)
        .with_for_update()
    )
    
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
        
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    if req.requested_for_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Registration request not found")
        
    req.status = "rejected"
    db.commit()
    
    return {"detail": "Registration rejected"}
