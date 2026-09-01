import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.actor import Actor
from app.models.repository import Repository
from app.models.user import User

router = APIRouter(
    prefix="/v1/repositories",
    tags=["repository-agents"],
)

DEFAULT_PERMISSIONS = [
    "repository.read",
    "repository.write",
    "change.create",
    "change.commit",
    "change.conflict.read",
    "knowledge_graph.read",
    "knowledge_graph.write",
]


class AgentAccessRequest(BaseModel):
    agent_id: str
    permissions: list[str] = Field(default_factory=lambda: DEFAULT_PERMISSIONS.copy())
    enabled: bool = True


class AgentAccessResponse(BaseModel):
    id: str
    agent_id: str
    repository_id: str
    agent_name: str
    permissions: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


def _repo_for_owner(
    owner: str,
    repo: str,
    current_user: User,
    db: Session,
) -> Repository:
    repository = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            Actor.name == owner,
            Repository.slug == repo.lower(),
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None or repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    return repository


def _serialize(
    access: AgentRepositoryAccess,
    agent: Agent,
) -> AgentAccessResponse:
    try:
        permissions = json.loads(access.permissions or "[]")
    except (TypeError, ValueError):
        permissions = []

    return AgentAccessResponse(
        id=access.id,
        agent_id=agent.id,
        repository_id=access.repository_id,
        agent_name=agent.name,
        permissions=permissions if isinstance(permissions, list) else [],
        enabled=access.enabled,
        created_at=access.created_at,
        updated_at=access.updated_at,
    )


@router.get(
    "/{owner}/{repo}/agents",
    response_model=list[AgentAccessResponse],
    summary="List Agent Repository Grants (Human JWT required)",
    description="Lists all agents that have been granted access to this repository. Only the human repository owner can call this.",
)
def list_repository_agents(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _repo_for_owner(owner, repo, current_user, db)

    rows = db.execute(
        select(AgentRepositoryAccess, Agent)
        .join(Agent, Agent.id == AgentRepositoryAccess.agent_id)
        .where(
            AgentRepositoryAccess.repository_id == repository.id,
            Agent.owner_id == current_user.id,
        )
        .order_by(Agent.created_at.desc())
    ).all()

    return [_serialize(access, agent) for access, agent in rows]


@router.post(
    "/{owner}/{repo}/agents",
    response_model=AgentAccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant Agent Repository Access (Human JWT required)",
    description="Grants an agent access to a repository. Only the human repository owner can call this. Agents CANNOT grant themselves access.",
)
def grant_repository_agent_access(
    owner: str,
    repo: str,
    payload: AgentAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _repo_for_owner(owner, repo, current_user, db)

    agent = db.scalar(
        select(Agent).where(
            Agent.id == payload.agent_id,
            Agent.owner_id == current_user.id,
            Agent.is_active.is_(True),
        )
    )

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    allowed = set(DEFAULT_PERMISSIONS)
    unknown = set(payload.permissions) - allowed
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported permissions: {sorted(unknown)}",
        )

    existing = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.agent_id == agent.id,
            AgentRepositoryAccess.repository_id == repository.id,
        )
    )

    if existing is None:
        existing = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps(payload.permissions),
            enabled=payload.enabled,
        )
        db.add(existing)
    else:
        existing.permissions = json.dumps(payload.permissions)
        existing.enabled = payload.enabled
        existing.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(existing)

    return _serialize(existing, agent)


@router.delete(
    "/{owner}/{repo}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_repository_agent_access(
    owner: str,
    repo: str,
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _repo_for_owner(owner, repo, current_user, db)

    access = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.repository_id == repository.id,
            AgentRepositoryAccess.agent_id == agent_id,
        )
    )

    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent repository access not found",
        )

    db.delete(access)
    db.commit()
