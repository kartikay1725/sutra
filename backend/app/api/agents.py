import secrets
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.agent_dependencies import (
    authenticate_agent_token,
    create_agent_session,
    get_current_agent,
    get_current_agent_session,
    revoke_agent_session,
    SESSION_TTL_MINUTES,
    SESSION_IDLE_TIMEOUT_SECONDS,
)
from app.models.agent_session import AgentSession

from app.api.dependencies import get_current_user
from app.core.security import hash_password, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models.agent import Agent
from app.models.user import User
from app.models.actor import Actor


router = APIRouter(
    prefix="/v1/agents",
    tags=["agents"],
)


class CreateAgentRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        max_length=2000,
    )

    provider: str | None = Field(
        default=None,
        max_length=120,
    )

    model: str | None = Field(
        default=None,
        max_length=120,
    )


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    provider: str | None
    model: str | None
    status: str
    is_active: bool
    token_prefix: str


class AgentCreatedResponse(AgentResponse):
    token: str


class CreateAgentSessionRequest(BaseModel):
    token: str = Field(
        min_length=20,
        max_length=255,
    )


class AgentSessionResponse(BaseModel):
    session_id: str
    agent_id: str
    token: str
    token_prefix: str
    status: str
    expires_at: datetime
    last_seen_at: datetime


class AgentHeartbeatResponse(BaseModel):
    session_id: str
    agent_id: str
    status: str
    expires_at: datetime
    last_seen_at: datetime


class AgentSessionRevokeResponse(BaseModel):
    session_id: str
    agent_id: str
    status: str
    revoked_at: datetime | None


@router.post(
    "",
    response_model=AgentCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Agent (Human JWT required)",
    description="Creates a new Agent. Returns a permanent agent token ONCE. This token must be stored securely and exchanged for AgentSessions.",
)
def create_agent(
    payload: CreateAgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = "sutra_agent_" + secrets.token_urlsafe(32)

    agent = Agent(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        provider=payload.provider,
        model=payload.model,
        token_hash=hash_password(token),
        token_prefix=token[:16],
        status="active",
        is_active=True,
    )

    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=current_user.id,
        capabilities=(
            '["repository.read",'
            '"repository.write",'
            '"change.create",'
            '"change.commit",'
            '"change.conflict.read"]'
        ),
    )
    db.add(actor)
    db.commit()
    db.refresh(agent)

    return AgentCreatedResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        provider=agent.provider,
        model=agent.model,
        status=agent.status,
        is_active=agent.is_active,
        token_prefix=agent.token_prefix,
        token=token,
    )


class SpawnAgentRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )


@router.post(
    "/spawn",
    response_model=AgentCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Spawn Sub-Agent",
    description="Allows an active Agent to spawn a sub-agent. Returns a permanent sub-agent token ONCE.",
)
def spawn_sub_agent(
    payload: SpawnAgentRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    token = "sutra_subagent_" + secrets.token_urlsafe(32)

    sub_agent = Agent(
        owner_id=current_agent.owner_id,
        parent_agent_id=current_agent.id,
        name=payload.name,
        description=payload.description,
        provider=current_agent.provider,
        model=current_agent.model,
        token_hash=hash_password(token),
        token_prefix=token[:16],
        status="active",
        is_active=True,
    )

    db.add(sub_agent)
    db.flush()

    actor = Actor(
        id=sub_agent.id,
        type="agent",
        name=sub_agent.name,
        owner_id=current_agent.owner_id,
        capabilities=(
            '["repository.read",'
            '"repository.write",'
            '"change.create",'
            '"change.commit",'
            '"change.conflict.read"]'
        ),
    )
    db.add(actor)
    db.commit()
    db.refresh(sub_agent)

    return AgentCreatedResponse(
        id=sub_agent.id,
        name=sub_agent.name,
        description=sub_agent.description,
        provider=sub_agent.provider,
        model=sub_agent.model,
        status=sub_agent.status,
        is_active=sub_agent.is_active,
        token_prefix=sub_agent.token_prefix,
        token=token,
    )



@router.get(
    "",
    response_model=list[AgentResponse],
    summary="List Agents (Human JWT required)",
    description="Lists all agents owned by the authenticated human user.",
)
def list_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agents = db.scalars(
        select(Agent)
        .where(Agent.owner_id == current_user.id)
        .order_by(Agent.created_at.desc())
    ).all()

    return [
        AgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            provider=agent.provider,
            model=agent.model,
            status=agent.status,
            is_active=agent.is_active,
            token_prefix=agent.token_prefix,
        )
        for agent in agents
    ]


@router.post(
    "/session",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AgentSession",
    description="Exchange a permanent agent credential for a short-lived AgentSession. The returned AgentSession token is used as the Bearer token for all agent endpoints and as the password for Git HTTP. Expiry is 15 minutes absolute, 120 seconds idle.",
)
def create_session(
    payload: CreateAgentSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Exchange a long-lived agent credential for a short-lived session.
    """
    from app.core.rate_limit import enforce_rate_limit, get_client_ip
    ip = get_client_ip(request)
    enforce_rate_limit(f"agent_session:ip:{ip}", 30, 900, "session creation")

    agent = authenticate_agent_token(
        payload.token,
        db,
    )

    enforce_rate_limit(
        f"agent_session:agent:{agent.id}",
        settings.rate_limit_agent_session_per_15min,
        900,
        "session creation",
    )

    session, session_token = create_agent_session(
        agent,
        db,
    )

    return AgentSessionResponse(
        session_id=session.id,
        agent_id=agent.id,
        token=session_token,
        token_prefix=session.token_prefix,
        status=session.status,
        expires_at=session.expires_at,
        last_seen_at=session.last_seen_at,
    )


@router.post(
    "/sessions/{session_id}/revoke",
    response_model=AgentSessionRevokeResponse,
    summary="Revoke AgentSession (Owner)",
    description="Revoke one session belonging to an agent owned by the current user. Requires Human JWT.",
)
def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke one session belonging to an agent owned by the current user.
    """

    session = db.scalar(
        select(AgentSession).join(
            Agent,
            Agent.id == AgentSession.agent_id,
        ).where(
            AgentSession.id == session_id,
            Agent.owner_id == current_user.id,
        )
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent session not found",
        )

    session = revoke_agent_session(
        session,
        db,
    )

    return AgentSessionRevokeResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        status=session.status,
        revoked_at=session.revoked_at,
    )


@router.post(
    "/session/revoke",
    response_model=AgentSessionRevokeResponse,
    summary="Revoke Current AgentSession",
    description="Allow an authenticated agent to terminate its own active session.",
)
def revoke_current_session(
    current_session: AgentSession = Depends(
        get_current_agent_session
    ),
    db: Session = Depends(get_db),
):
    """
    Allow an authenticated agent to terminate its own session.
    """

    session = revoke_agent_session(
        current_session,
        db,
    )

    return AgentSessionRevokeResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        status=session.status,
        revoked_at=session.revoked_at,
    )


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    summary="AgentSession Heartbeat",
    description="Explicit liveness heartbeat. External agents should send this approximately every 30-60 seconds. The server considers a session inactive after more than 120 seconds without a successful authenticated request.",
)
def heartbeat(
    current_session: AgentSession = Depends(
        get_current_agent_session
    ),
):
    """
    Explicit liveness heartbeat.

    External agents should send this approximately every
    30-60 seconds.

    The server considers a session inactive after more than
    120 seconds without a successful authenticated request.
    """

    return AgentHeartbeatResponse(
        session_id=current_session.id,
        agent_id=current_session.agent_id,
        status=current_session.status,
        expires_at=current_session.expires_at,
        last_seen_at=current_session.last_seen_at,
    )


@router.get(
    "/me",
    response_model=AgentResponse,
    summary="Get Current Agent",
    description="Returns details about the currently authenticated agent.",
)
def agent_me(
    current_agent: Agent = Depends(get_current_agent),
):
    return AgentResponse(
        id=current_agent.id,
        name=current_agent.name,
        description=current_agent.description,
        provider=current_agent.provider,
        model=current_agent.model,
        status=current_agent.status,
        is_active=current_agent.is_active,
        token_prefix=current_agent.token_prefix,
    )


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Agent (Owner)",
    description="Permanently revokes an agent. The agent's permanent token is invalidated. Requires Human JWT.",
)
def revoke_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == current_user.id,
        )
    )

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    agent.is_active = False
    agent.status = "revoked"
    agent.updated_at = datetime.now(timezone.utc)

    db.commit()


# ---------------------------------------------------------
# Repository Access Management by Agent
# ---------------------------------------------------------

class AgentRepositoryAccessListItem(BaseModel):
    id: str
    repository_id: str
    repository_name: str
    repository_slug: str
    repository_owner: str
    permissions: list[str]
    enabled: bool

class GrantAgentRepositoryAccessRequest(BaseModel):
    repository_id: str
    permissions: list[str]
    enabled: bool = True

class UpdateAgentRepositoryAccessRequest(BaseModel):
    permissions: list[str]
    enabled: bool = True


@router.get(
    "/{agent_id}/repository-access",
    response_model=list[AgentRepositoryAccessListItem],
)
def list_agent_repository_access(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == current_user.id,
        )
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from app.models.agent_repository_access import AgentRepositoryAccess
    from app.models.repository import Repository
    from app.models.actor import Actor
    import json

    rows = db.execute(
        select(AgentRepositoryAccess, Repository, Actor)
        .join(Repository, Repository.id == AgentRepositoryAccess.repository_id)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(AgentRepositoryAccess.agent_id == agent.id)
    ).all()

    res = []
    for access, repo, owner_actor in rows:
        try:
            permissions = json.loads(access.permissions or "[]")
        except Exception:
            permissions = []
        res.append(
            AgentRepositoryAccessListItem(
                id=access.id,
                repository_id=repo.id,
                repository_name=repo.name,
                repository_slug=repo.slug,
                repository_owner=owner_actor.name,
                permissions=permissions if isinstance(permissions, list) else [],
                enabled=access.enabled,
            )
        )
    return res


@router.post(
    "/{agent_id}/repository-access",
    response_model=AgentRepositoryAccessListItem,
    status_code=status.HTTP_201_CREATED,
)
def grant_agent_repository_access(
    agent_id: str,
    payload: GrantAgentRepositoryAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == current_user.id,
        )
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from app.models.repository import Repository
    repository = db.scalar(
        select(Repository).where(
            Repository.id == payload.repository_id,
            Repository.deleted_at.is_(None),
        )
    )
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.models.agent_repository_access import AgentRepositoryAccess
    from app.models.actor import Actor
    import json

    existing = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.agent_id == agent.id,
            AgentRepositoryAccess.repository_id == repository.id,
        )
    )

    if existing:
        existing.permissions = json.dumps(payload.permissions)
        existing.enabled = payload.enabled
        existing.updated_at = datetime.now(timezone.utc)
    else:
        existing = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps(payload.permissions),
            enabled=payload.enabled,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)

    owner_actor = db.scalar(select(Actor).where(Actor.id == repository.owner_id))
    owner_name = owner_actor.name if owner_actor else "Unknown"

    return AgentRepositoryAccessListItem(
        id=existing.id,
        repository_id=repository.id,
        repository_name=repository.name,
        repository_slug=repository.slug,
        repository_owner=owner_name,
        permissions=payload.permissions,
        enabled=existing.enabled,
    )


@router.put(
    "/{agent_id}/repository-access/{repository_id}",
    response_model=AgentRepositoryAccessListItem,
)
def update_agent_repository_access(
    agent_id: str,
    repository_id: str,
    payload: UpdateAgentRepositoryAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == current_user.id,
        )
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from app.models.agent_repository_access import AgentRepositoryAccess
    from app.models.repository import Repository
    from app.models.actor import Actor
    import json

    access = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.agent_id == agent.id,
            AgentRepositoryAccess.repository_id == repository_id,
        )
    )
    if not access:
        raise HTTPException(status_code=404, detail="Access grant not found")

    access.permissions = json.dumps(payload.permissions)
    access.enabled = payload.enabled
    access.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(access)

    repo = db.scalar(select(Repository).where(Repository.id == repository_id))
    owner_actor = db.scalar(select(Actor).where(Actor.id == repo.owner_id)) if repo else None
    owner_name = owner_actor.name if owner_actor else "Unknown"

    return AgentRepositoryAccessListItem(
        id=access.id,
        repository_id=repository_id,
        repository_name=repo.name if repo else "Unknown",
        repository_slug=repo.slug if repo else "unknown",
        repository_owner=owner_name,
        permissions=payload.permissions,
        enabled=access.enabled,
    )


@router.delete(
    "/{agent_id}/repository-access/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_agent_repository_access(
    agent_id: str,
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == current_user.id,
        )
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from app.models.agent_repository_access import AgentRepositoryAccess

    access = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.agent_id == agent.id,
            AgentRepositoryAccess.repository_id == repository_id,
        )
    )
    if not access:
        raise HTTPException(status_code=404, detail="Access grant not found")

    db.delete(access)
    db.commit()


# ---------------------------------------------------------------------------
# AGENT CONTEXT ENDPOINT (Phase 5B)
# ---------------------------------------------------------------------------

class ContextRepositoryAccess(BaseModel):
    repository_id: str
    owner: str
    slug: str
    provider: str
    capabilities: list[str]
    enabled: bool


class ContextSession(BaseModel):
    session_id: str
    expires_at: datetime
    idle_timeout_seconds: int
    absolute_ttl_minutes: int


class ContextIdentity(BaseModel):
    agent_id: str
    actor_id: str
    agent_name: str
    status: str


class ContextLifecycle(BaseModel):
    open_changes: int
    open_pull_requests: int
    pending_reviews: int


class ContextAllowedAction(BaseModel):
    name: str
    method: str
    endpoint: str
    description: str = ""
    requires: list[str] = []


class ContextNextAction(BaseModel):
    name: str
    method: str
    endpoint: str
    reason: str


class AgentContextResponse(BaseModel):
    """
    Machine-readable per-session context for autonomous agents.

    This endpoint is informational only. It reads SUTRA state and returns
    what the agent is currently allowed to do and what it should do next.
    It never grants authority.
    """
    protocol_version: str
    identity: ContextIdentity
    session: ContextSession
    repository_access: list[ContextRepositoryAccess]
    current_lifecycle: ContextLifecycle
    allowed_actions: list[ContextAllowedAction]
    blocked_actions: list[dict]
    next_recommended_action: ContextNextAction | None


@router.get(
    "/context",
    response_model=AgentContextResponse,
    summary="Agent Context (Agent session required)",
    description=(
        "Returns machine-readable, per-session state for an autonomous agent. "
        "Includes identity, session timing, repository access and capabilities, "
        "current lifecycle summary, allowed actions, and recommended next action. "
        "This endpoint is strictly informational: it reads state and never grants authority."
    ),
    tags=["agent-context"],
)
def get_agent_context(
    current_session: AgentSession = Depends(get_current_agent_session),
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> AgentContextResponse:
    from app.models.agent_repository_access import AgentRepositoryAccess
    from app.models.repository import Repository
    from app.models.change import Change
    from app.models.pull_request import PullRequest
    from app.models.change_review import ChangeReview

    # --- Repository access ---
    access_rows = db.execute(
        select(AgentRepositoryAccess, Repository)
        .join(Repository, Repository.id == AgentRepositoryAccess.repository_id)
        .where(
            AgentRepositoryAccess.agent_id == current_agent.id,
            AgentRepositoryAccess.enabled.is_(True),
            Repository.deleted_at.is_(None),
        )
    ).all()

    repo_access = []
    allowed_capabilities: set[str] = set()
    has_any_repo = len(access_rows) > 0
    has_write = False
    has_change_create = False

    for access, repo in access_rows:
        try:
            perms = json.loads(access.permissions or "[]")
        except Exception:
            perms = []
        caps = perms if isinstance(perms, list) else []
        allowed_capabilities.update(caps)
        if "repository.write" in caps:
            has_write = True
        if "change.create" in caps:
            has_change_create = True

        # Resolve owner name from Actor
        owner_actor = db.scalar(
            select(Actor).where(Actor.id == repo.owner_id)
        )
        repo_access.append(
            ContextRepositoryAccess(
                repository_id=repo.id,
                owner=owner_actor.name if owner_actor else "",
                slug=repo.slug,
                provider=repo.provider if hasattr(repo, "provider") else "local",
                capabilities=caps,
                enabled=access.enabled,
            )
        )

    # --- Lifecycle summary ---
    open_changes = db.scalar(
        select(func.count(Change.id)).where(
            Change.actor_id == current_agent.id,
            Change.status.in_(["proposed", "recorded"]),
        )
    ) or 0

    open_prs = db.scalar(
        select(func.count(PullRequest.id)).where(
            PullRequest.author_id == current_agent.id,
            PullRequest.status.in_(["draft", "open"]),
        )
    ) or 0

    # Reviews awaiting human action (changes this agent authored, with approved review)
    pending_reviews = db.scalar(
        select(func.count(ChangeReview.id)).where(
            ChangeReview.reviewer_id == current_agent.id,
            ChangeReview.status == "pending",
        )
    ) or 0

    # --- Allowed actions (based on actual capabilities) ---
    allowed_actions: list[ContextAllowedAction] = [
        ContextAllowedAction(
            name="get_context",
            method="GET",
            endpoint="/v1/agent/context",
            description="Refresh your authoritative SUTRA state and legal next action.",
        ),
        ContextAllowedAction(
            name="discover_protocol",
            method="POST",
            endpoint="/v1/agent-protocol/handshake",
            description="Read the SUTRA agent protocol contract.",
        ),
    ]

    blocked_actions: list[dict] = []

    if has_any_repo and "repository.read" in allowed_capabilities:
        allowed_actions.append(ContextAllowedAction(
            name="get_repository_credential",
            method="POST",
            endpoint="/v1/repositories/{owner}/{repo}/token",
            description="Obtain a scoped downstream credential for Git operations.",
            requires=["repository.read"],
        ))

    if has_write:
        allowed_actions.append(
            ContextAllowedAction(
                name="create_pull_request",
                method="POST",
                endpoint="/v1/pull-requests/agent",
                description="Create a Pull Request from one of your Changes.",
                requires=["repository.write", "change.create"],
            )
        )

    if has_change_create:
        allowed_actions.append(
            ContextAllowedAction(
                name="create_change",
                method="POST",
                endpoint="/v1/changes/agent",
                description="Create a Change record for your engineering intent.",
                requires=["change.create"],
            )
        )

        allowed_actions.append(
            ContextAllowedAction(
                name="attach_commit",
                method="POST",
                endpoint="/v1/changes/{id}/agent-commit",
                description="Attach the resulting commit SHA to your Change.",
                requires=["change.commit"],
            )
        )

        allowed_actions.append(
            ContextAllowedAction(
                name="finalize_change",
                method="POST",
                endpoint="/v1/changes/{id}/agent-finalize",
                description="Finalize your Change after the resulting commit is recorded.",
                requires=["change.commit", "change.create"],
            )
        )

    if not has_any_repo:
        blocked_actions.append({
            "action": "any_repository_operation",
            "reason": "REPOSITORY_ACCESS_REQUIRED",
            "detail": "No repository access grants exist for this agent. "
                      "A human repository owner must grant access via "
                      "POST /v1/repositories/{owner}/{repo}/agents.",
        })

    blocked_actions.append({
        "action": "merge_pull_request",
        "reason": "HUMAN_APPROVAL_REQUIRED",
        "detail": "Agents cannot trigger merge directly. "
                  "POST /v1/pull-requests/{id}/merge requires human approval first. "
                  "Agents can submit reviews/findings but cannot self-approve.",
    })

    blocked_actions.append({
        "action": "approve_pull_request",
        "reason": "AGENT_ACTION_FORBIDDEN",
        "detail": "Agents cannot approve their own changes. "
                  "Human reviewer approval is always required.",
    })

    # --- Next recommended action ---
    next_action: ContextNextAction | None = None
    if not has_any_repo:
        next_action = ContextNextAction(
            name="wait_for_repository_access",
            method="GET",
            endpoint="/v1/agent/context",
            reason=(
                "No enabled repository access grant is available. "
                "A human repository owner must grant access. "
                "Refresh this context to detect when access is granted."
            ),
        )
    elif open_changes == 0:
        next_action = ContextNextAction(
            name="create_change",
            method="POST",
            endpoint="/v1/changes/agent",
            reason="No open Changes. Create a Change to begin recording your engineering intent.",
        )
    elif open_prs == 0 and open_changes > 0:
        next_action = ContextNextAction(
            name="create_pull_request",
            method="POST",
            endpoint="/v1/pull-requests/agent",
            reason="Change exists without a Pull Request. Create a PR to start the review workflow.",
        )
    else:
        next_action = ContextNextAction(
            name="poll_pull_request_status",
            method="GET",
            endpoint="/v1/pull-requests/agent",
            reason="Pull Request is open. Poll for status changes. Stop when human approval is required.",
        )

    return AgentContextResponse(
        protocol_version="1",
        identity=ContextIdentity(
            agent_id=current_agent.id,
            actor_id=current_agent.id,
            agent_name=current_agent.name,
            status=current_agent.status,
        ),
        session=ContextSession(
            session_id=current_session.id,
            expires_at=current_session.expires_at,
            idle_timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
            absolute_ttl_minutes=SESSION_TTL_MINUTES,
        ),
        repository_access=repo_access,
        current_lifecycle=ContextLifecycle(
            open_changes=open_changes,
            open_pull_requests=open_prs,
            pending_reviews=pending_reviews,
        ),
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        next_recommended_action=next_action,
    )