from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from pathlib import Path

from typing import Any
from app.api.dependencies import get_current_user, get_current_user_optional
from app.api.agent_dependencies import get_current_agent_session
from app.core.config import settings
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.models.actor import Actor
from app.services.repository_service import RepositoryService
from app.services.repository_browser_service import RepositoryBrowserService, RepositoryBrowserError


router = APIRouter(
    prefix="/v1/repositories",
    tags=["repositories"],
)


class CreateRepositoryRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
    )

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    visibility: str = "private"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_repository(
    payload: CreateRepositoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.visibility not in {
        "public",
        "private",
    }:
        raise HTTPException(
            status_code=400,
            detail="Invalid visibility",
        )

    try:
        repository = RepositoryService(
            db
        ).create(
            owner_id=current_user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "id": repository.id,
        "name": repository.name,
        "owner": current_user.username,
        "visibility": repository.visibility,
        "default_branch": repository.default_branch,
        "clone_url": (
            f"{settings.sutra_base_url}/git/"
            f"{current_user.username}/"
            f"{repository.name}.git"
        ),
    }


@router.get("/{owner}/{repo}")
def get_repository(
    owner: str,
    repo: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(
            Actor,
            Actor.id == Repository.owner_id,
        )
        .where(
            Actor.name == owner,
            Repository.slug == repo.lower(),
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    if repository.visibility == "private":
        if not current_user or repository.owner_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="Repository not found",
            )

    return {
        "id": repository.id,
        "name": repository.name,
        "owner": owner,
        "description": repository.description,
        "visibility": repository.visibility,
        "default_branch": repository.default_branch,
        "settings": repository.settings or {},
        "created_at": repository.created_at.isoformat() if repository.created_at else None,
        "updated_at": repository.updated_at.isoformat() if repository.updated_at else None,
    }


@router.get("")
def list_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repositories = db.scalars(
        select(Repository)
        .where(
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
        .order_by(Repository.updated_at.desc())
    ).all()

    return [
        {
            "id": repo.id,
            "name": repo.name,
            "owner": current_user.username,
            "description": repo.description,
            "visibility": repo.visibility,
            "default_branch": repo.default_branch,
            "settings": repo.settings or {},
            "provider_type": getattr(repo, "provider_type", "local") or "local",
            "external_id": getattr(repo, "external_id", None),
            "provider_owner": getattr(repo, "provider_owner", None),
            "created_at": repo.created_at.isoformat() if repo.created_at else None,
            "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
        }
        for repo in repositories
    ]


class UpdateSettingsRequest(BaseModel):
    settings: dict | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    description: str | None = None
    default_branch: str | None = None

@router.patch("/{owner}/{repo}/settings")
def update_repository_settings(
    owner: str,
    repo: str,
    payload: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            Actor.name == owner,
            Repository.slug == repo.lower(),
            Repository.deleted_at.is_(None)
        )
    )

    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )
    
    if payload.name and payload.name != repository.name:
        # Check uniqueness for owner
        existing = db.scalar(
            select(Repository).where(
                Repository.owner_id == current_user.id,
                Repository.slug == payload.name.lower(),
                Repository.id != repository.id,
                Repository.deleted_at.is_(None),
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Repository with this name already exists")
        repository.name = payload.name
        repository.slug = payload.name.lower()

    if payload.description is not None:
        repository.description = payload.description

    if payload.default_branch is not None:
        branch = payload.default_branch.strip()
        if not branch:
            raise HTTPException(status_code=400, detail="Default branch cannot be empty")
        try:
            RepositoryBrowserService(
                (Path(settings.repository_storage_path).resolve() / repository.storage_key).resolve()
            ).resolve_commit(branch)
        except (RepositoryBrowserError, OSError):
            raise HTTPException(status_code=400, detail="Default branch does not exist")
        repository.default_branch = branch

    if payload.settings is not None:
        repository.settings = payload.settings
        
    db.commit()
    db.refresh(repository)
    
    return {
        "status": "ok",
        "name": repository.name,
        "description": repository.description,
        "default_branch": repository.default_branch,
        "settings": repository.settings,
    }

from datetime import datetime, timezone

@router.delete("/{owner}/{repo}")
def delete_repository(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            Actor.name == owner,
            Repository.slug == repo.lower(),
            Repository.deleted_at.is_(None)
        )
    )

    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    repository.deleted_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"status": "deleted"}

class VisibilityRequest(BaseModel):
    visibility: str

@router.patch("/{owner}/{repo}/visibility")
def update_visibility(
    owner: str,
    repo: str,
    payload: VisibilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(Actor.name == owner, Repository.slug == repo.lower(), Repository.deleted_at.is_(None))
    )

    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    if payload.visibility not in {"public", "private"}:
        raise HTTPException(status_code=400, detail="Invalid visibility")

    repository.visibility = payload.visibility
    db.commit()
    return {"status": "ok", "visibility": repository.visibility}

@router.patch("/{owner}/{repo}/archive")
def archive_repository(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(Actor.name == owner, Repository.slug == repo.lower(), Repository.deleted_at.is_(None))
    )

    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Toggle archive state by putting it in settings for now
    settings = repository.settings or {}
    settings["archived"] = True
    # SQLAlchemy JSON needs to be reassigned to trigger change
    repository.settings = dict(settings)
    db.commit()
    return {"status": "archived"}

class TransferRequest(BaseModel):
    new_owner: str

@router.post("/{owner}/{repo}/transfer")
def transfer_repository(
    owner: str,
    repo: str,
    payload: TransferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(Actor.name == owner, Repository.slug == repo.lower(), Repository.deleted_at.is_(None))
    )

    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    new_owner_actor = db.scalar(select(Actor).where(Actor.name == payload.new_owner))
    if not new_owner_actor:
        raise HTTPException(status_code=404, detail="Target user not found")

    repository.owner_id = new_owner_actor.id
    db.commit()
    return {"status": "transferred"}


class RepositoryTokenRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=lambda: ["repository.read"])
    max_ttl_seconds: int = Field(default=600, ge=60, le=600)


class RepositoryTokenResponse(BaseModel):
    token: str
    token_type: str
    expires_at: datetime
    effective_ttl_seconds: int
    repository: str
    permissions: dict[str, str]
    clone_url: str


@router.post(
    "/{owner}/{repo}/token",
    response_model=RepositoryTokenResponse,
    summary="Issue Downstream Transport Credential (AgentSession required)",
    description=(
        "Exchanges an active SUTRA AgentSession for an ephemeral downstream transport credential. "
        "Strictly bounded to single repository, minimum capability permissions, and effective TTL <= 10 min."
    ),
)
def issue_repository_token(
    owner: str,
    repo: str,
    payload: RepositoryTokenRequest,
    current_session: Any = Depends(get_current_agent_session),
    db: Session = Depends(get_db),
):
    from app.services.authorization_service import AuthorizationService
    from app.providers.local.credentials import LocalCredentialProvider
    from app.providers.github.credentials import GitHubCredentialProvider
    from app.providers.github.auth import GitHubAppAuthService
    from app.providers.registry import ProviderRegistry

    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(Actor.name == owner, Repository.slug == repo.lower(), Repository.deleted_at.is_(None))
    )
    if not repository:
        # Also check direct slug lookup
        repository = db.scalar(
            select(Repository).where(Repository.slug == repo.lower(), Repository.deleted_at.is_(None))
        )
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    actor = db.scalar(select(Actor).where(Actor.id == current_session.agent_id, Actor.type == "agent"))
    if not actor:
        from app.api.agent_errors import raise_agent_inactive
        raise_agent_inactive()

    # Authorize each requested capability
    from app.api.agent_errors import raise_capability_required
    for cap in payload.capabilities:
        decision = AuthorizationService.check(actor=actor, repository=repository, capability=cap, db=db)
        if not decision.allowed:
            raise_capability_required(
                capability=cap,
                repository_slug=repository.slug if repository else repo,
            )

    # Build credential provider
    app_id = getattr(settings, "github_app_id", None) or "0"
    pem = getattr(settings, "github_private_key_pem", None) or ""
    auth_service = GitHubAppAuthService(app_id=app_id, private_key_pem=pem)
    local_cred = LocalCredentialProvider(db)
    github_cred = GitHubCredentialProvider(auth_service)

    registry = ProviderRegistry(
        repository_providers={},
        credential_providers={"local": local_cred, "github": github_cred},
        webhook_adapters={},
        check_providers={},
        default_provider="local",
    )

    cred_provider = registry.get_credential_provider(repository)
    downstream = cred_provider.issue_agent_token(
        agent_id=current_session.agent_id,
        session_id=current_session.id,
        owner=owner,
        repo=repo,
        sutra_capabilities=payload.capabilities,
        max_ttl_seconds=payload.max_ttl_seconds,
    )

    return RepositoryTokenResponse(
        token=downstream.token,
        token_type=downstream.token_type,
        expires_at=downstream.expires_at,
        effective_ttl_seconds=downstream.effective_ttl_seconds,
        repository=downstream.repository,
        permissions=downstream.permissions,
        clone_url=downstream.clone_url,
    )
