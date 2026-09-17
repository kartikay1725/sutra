import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
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

logger = logging.getLogger("sutra.api.repositories")

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
    summary="Create Repository",
    description="Initializes a new bare Git repository under SUTRA governance.",
)
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_repository_endpoint(
    payload: CreateRepositoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.visibility not in {"public", "private"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid visibility: must be 'public' or 'private'",
        )

    try:
        repository = RepositoryService(db).create(
            owner_id=current_user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409 if "already exists" in str(exc) else 400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create repository: {str(exc)}",
        ) from exc

    github_clone_url = (
        repository.upstream_url
        if repository.upstream_url and "github.com" in repository.upstream_url
        else f"https://github.com/{repository.provider_owner or current_user.username}/{repository.name}.git"
    )

    return {
        "id": repository.id,
        "name": repository.name,
        "slug": repository.slug,
        "owner": current_user.username,
        "description": repository.description,
        "visibility": repository.visibility,
        "default_branch": repository.default_branch,
        "connection_type": getattr(repository, "connection_type", "owned") or "owned",
        "upstream_url": getattr(repository, "upstream_url", None),
        "upstream_repository_id": getattr(repository, "upstream_repository_id", None),
        "clone_url": github_clone_url,
        "created_at": repository.created_at.isoformat() if repository.created_at else None,
    }


class CloneRepositoryRequest(BaseModel):
    url: str = Field(
        min_length=1,
        max_length=1000,
        description="Git repository clone URL or owner/name shorthand",
    )
    name: str | None = Field(
        default=None,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )
    visibility: str = "private"


@router.post(
    "/clone",
    status_code=status.HTTP_201_CREATED,
    summary="Clone Repository into SUTRA",
    description="Clones any Git URL or repository into SUTRA storage, installs SUTRA pre-receive policy hook, and registers repository record.",
)
def clone_repository_endpoint(
    payload: CloneRepositoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.visibility not in {
        "public",
        "private",
    }:
        raise HTTPException(
            status_code=400,
            detail="Invalid visibility: must be 'public' or 'private'",
        )

    try:
        repository = RepositoryService(db).clone_repository(
            owner_id=current_user.id,
            url=payload.url,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409 if "already exists" in str(exc) else 400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone repository: {str(exc)}",
        ) from exc

    return {
        "id": repository.id,
        "name": repository.name,
        "owner": current_user.username,
        "visibility": repository.visibility,
        "default_branch": repository.default_branch,
        "connection_type": repository.connection_type,
        "upstream_url": repository.upstream_url,
        "upstream_repository_id": repository.upstream_repository_id,
        "clone_url": (
            repository.upstream_url
            if repository.upstream_url and "github.com" in repository.upstream_url
            else f"https://github.com/{repository.provider_owner or current_user.username}/{repository.name}.git"
        ),
    }


@router.get("/{owner}/{repo}")
def get_repository(
    owner: str,
    repo: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Repository)
        .join(
            Actor,
            Actor.id == Repository.owner_id,
        )
        .where(
            (Actor.name == owner) | (Repository.provider_owner == owner),
            (Repository.slug == repo.lower()) | (Repository.name == repo) | (Repository.slug == f"{owner}/{repo}".lower()),
            Repository.deleted_at.is_(None),
        )
    )
    if current_user:
        stmt = stmt.order_by(
            (Repository.owner_id == current_user.id).desc(),
            (Repository.visibility == "public").desc(),
            Repository.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(
            (Repository.visibility == "public").desc(),
            Repository.created_at.desc(),
        )
    repository = db.scalar(stmt)

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

    github_owner = getattr(repository, "provider_owner", None) or owner
    github_clone_url = (
        repository.upstream_url
        if getattr(repository, "upstream_url", None) and "github.com" in repository.upstream_url
        else f"https://github.com/{github_owner}/{repository.name}.git"
    )

    return {
        "id": repository.id,
        "name": repository.name,
        "owner": owner,
        "description": repository.description,
        "visibility": repository.visibility,
        "default_branch": repository.default_branch,
        "connection_type": getattr(repository, "connection_type", "owned") or "owned",
        "upstream_url": getattr(repository, "upstream_url", None),
        "upstream_repository_id": getattr(repository, "upstream_repository_id", None),
        "provider_type": getattr(repository, "provider_type", "local") or "local",
        "provider_owner": getattr(repository, "provider_owner", None),
        "clone_url": github_clone_url,
        "settings": repository.settings or {},
        "created_at": repository.created_at.isoformat() if repository.created_at else None,
        "updated_at": repository.updated_at.isoformat() if repository.updated_at else None,
    }


@router.post(
    "/{owner}/{repo}/fork",
    status_code=status.HTTP_201_CREATED,
    summary="Fork Repository in SUTRA",
    description="Creates or connects a fork of an upstream repository for autonomous open-source contributions.",
)
def fork_repository_endpoint(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upstream = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            (Actor.name == owner) | (Repository.provider_owner == owner),
            (Repository.slug == repo.lower()) | (Repository.name == repo),
            Repository.deleted_at.is_(None),
        )
    )
    if not upstream:
        raise HTTPException(status_code=404, detail="Upstream repository not found")

    try:
        fork_repo = RepositoryService(db).create_or_connect_fork(
            owner_id=current_user.id,
            upstream_repository_id=upstream.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fork repository: {str(exc)}") from exc

    return {
        "id": fork_repo.id,
        "name": fork_repo.name,
        "owner": current_user.username,
        "visibility": fork_repo.visibility,
        "default_branch": fork_repo.default_branch,
        "connection_type": fork_repo.connection_type,
        "upstream_url": fork_repo.upstream_url,
        "upstream_repository_id": fork_repo.upstream_repository_id,
        "clone_url": f"https://github.com/{fork_repo.provider_owner or current_user.username}/{fork_repo.name}.git",
    }


@router.get("")
def list_repositories(
    q: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Repository).where(
        Repository.owner_id == current_user.id,
        Repository.deleted_at.is_(None),
    )
    if q and q.strip():
        query = query.where(Repository.name.ilike(f"%{q.strip()}%"))

    repositories = db.scalars(
        query.order_by(Repository.updated_at.desc())
    ).all()

    return [
        {
            "id": repo.id,
            "name": repo.name,
            "owner": current_user.username,
            "description": repo.description,
            "visibility": repo.visibility,
            "default_branch": repo.default_branch,
            "connection_type": getattr(repo, "connection_type", "owned") or "owned",
            "upstream_url": getattr(repo, "upstream_url", None),
            "upstream_repository_id": getattr(repo, "upstream_repository_id", None),
            "settings": repo.settings or {},
            "provider_type": getattr(repo, "provider_type", "local") or "local",
            "external_id": getattr(repo, "external_id", None),
            "provider_owner": getattr(repo, "provider_owner", None),
            "clone_url": (
                repo.upstream_url
                if getattr(repo, "upstream_url", None) and "github.com" in repo.upstream_url
                else f"https://github.com/{getattr(repo, 'provider_owner', None) or current_user.username}/{repo.name}.git"
            ),
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

def _resolve_repo_for_modification(
    owner: str,
    repo: str,
    current_user: User,
    db: Session,
) -> Repository:
    stmt = (
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            (Actor.name == owner) | (Repository.provider_owner == owner),
            (Repository.slug == repo.lower()) | (Repository.name == repo) | (Repository.slug == f"{owner}/{repo}".lower()),
            Repository.deleted_at.is_(None),
        )
    )
    repository = db.scalar(stmt)
    if not repository:
        # Fallback without actor join in case owner is direct provider_owner
        repository = db.scalar(
            select(Repository).where(
                (Repository.provider_owner == owner) | (Repository.name == repo) | (Repository.slug == repo.lower()) | (Repository.slug == f"{owner}/{repo}".lower()),
                Repository.deleted_at.is_(None),
            )
        )

    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )
    return repository


def _get_github_repo_provider(repository: Repository):
    if getattr(repository, "provider_type", "local") != "github" or not getattr(repository, "provider_owner", None):
        return None
    if not settings.github_app_id or not settings.github_private_key_pem:
        return None
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
    except Exception as exc:
        logger.warning("Failed to initialize GitHub provider: %s", exc)
        return None


@router.patch("/{owner}/{repo}/settings")
def update_repository_settings(
    owner: str,
    repo: str,
    payload: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _resolve_repo_for_modification(owner, repo, current_user, db)
    provider = _get_github_repo_provider(repository)
    github_sync = {"synced": False, "notice": None}

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

        # Sync rename to GitHub if provider-connected
        if provider:
            try:
                provider.update_repository(repository.provider_owner, repository.name, new_name=payload.name)
                github_sync["synced"] = True
            except Exception as exc:
                logger.warning("Could not sync repository rename to GitHub: %s", exc)
                github_sync["notice"] = (
                    "Repository renamed in SUTRA. Direct rename on GitHub requires GitHub App Administration permission."
                )

        repository.name = payload.name
        repository.slug = payload.name.lower()

    if payload.description is not None:
        if provider:
            try:
                provider.update_repository(repository.provider_owner, repository.name, description=payload.description)
                github_sync["synced"] = True
            except Exception as exc:
                logger.warning("Could not sync repository description to GitHub: %s", exc)
                if not github_sync["notice"]:
                    github_sync["notice"] = (
                        "Description updated in SUTRA. Direct sync to GitHub requires GitHub App Administration permission."
                    )
        repository.description = payload.description

    if payload.default_branch is not None:
        branch = payload.default_branch.strip()
        if not branch:
            raise HTTPException(status_code=400, detail="Default branch cannot be empty")
        
        if provider:
            # Validate branch existence on GitHub
            branch_info = provider.get_branch(repository.provider_owner, repository.name, branch)
            if not branch_info:
                all_branches = provider.list_branches(repository.provider_owner, repository.name)
                if not any(b.name == branch for b in all_branches):
                    raise HTTPException(status_code=400, detail=f"Default branch '{branch}' does not exist on GitHub")

            # Sync default branch to GitHub
            try:
                provider.update_repository(repository.provider_owner, repository.name, default_branch=branch)
                github_sync["synced"] = True
            except Exception as exc:
                logger.warning("Could not sync default_branch to GitHub: %s", exc)
                if not github_sync["notice"]:
                    github_sync["notice"] = (
                        "Default branch updated in SUTRA. Direct sync to GitHub requires GitHub App Administration permission."
                    )

            # Invalidate cached branch list
            try:
                from app.core.redis_service import redis_service
                redis_service.delete(f"github:cache:branches:{repository.id}")
            except Exception:
                pass
        else:
            try:
                RepositoryBrowserService(
                    (Path(settings.repository_storage_path).resolve() / repository.storage_key).resolve()
                ).resolve_commit(branch)
            except (RepositoryBrowserError, OSError):
                raise HTTPException(status_code=400, detail="Default branch does not exist")

        repository.default_branch = branch

    if payload.settings is not None:
        current_settings = dict(repository.settings or {})
        for k, v in payload.settings.items():
            if k == "policies" and isinstance(v, dict) and isinstance(current_settings.get("policies"), dict):
                merged_policies = dict(current_settings["policies"])
                merged_policies.update(v)
                current_settings["policies"] = merged_policies
            else:
                current_settings[k] = v
        repository.settings = current_settings
        
    db.commit()
    db.refresh(repository)
    
    return {
        "status": "ok",
        "name": repository.name,
        "description": repository.description,
        "default_branch": repository.default_branch,
        "settings": repository.settings,
        "provider_type": getattr(repository, "provider_type", "local") or "local",
        "github_sync": github_sync,
    }

from datetime import datetime, timezone

@router.delete("/{owner}/{repo}")
def delete_repository(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _resolve_repo_for_modification(owner, repo, current_user, db)
    provider = _get_github_repo_provider(repository)
    if provider:
        try:
            provider.delete_repository(repository.provider_owner, repository.name)
        except Exception as exc:
            logger.warning("Could not delete repo on GitHub: %s", exc)
    
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
    repository = _resolve_repo_for_modification(owner, repo, current_user, db)
    
    if payload.visibility not in {"public", "private"}:
        raise HTTPException(status_code=400, detail="Invalid visibility")

    provider = _get_github_repo_provider(repository)
    if provider:
        try:
            provider.update_repository(
                repository.provider_owner,
                repository.name,
                is_private=(payload.visibility == "private"),
            )
        except Exception as exc:
            logger.warning("Could not sync visibility to GitHub: %s", exc)

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
    repository = _resolve_repo_for_modification(owner, repo, current_user, db)
    
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
    repository = _resolve_repo_for_modification(owner, repo, current_user, db)
    
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
