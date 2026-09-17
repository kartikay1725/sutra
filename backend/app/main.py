from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.agents import router as agents_router
from app.api.agent_messages import router as agent_messages_router
from app.api.agent_registration import router as agent_registration_router
from app.api.agent_repository_access import router as agent_repository_access_router
from app.api.agent_protocol import router as agent_protocol_router
from app.api.agent_tasks import (
    router as agent_tasks_router,
)
from app.api.agent_issues import router as agent_issues_router
from app.api.agent_sessions import (
    router as agent_sessions_router,
)
from app.api.auth import router as auth_router
from app.api.branch_protection import router as branch_protection_router
from app.api.ci import router as ci_router
from app.api.change_dependencies import (
    router as change_graph_router,
)
from app.api.change_policy import (
    router as change_policy_router,
)
from app.api.change_reviews import (
    router as change_reviews_router,
)
from app.api.discussions import router as discussions_router
from app.api.issues import router as issues_router
from app.api.knowledge_graph import router as knowledge_graph_router
from app.api.pull_requests import (
    router as pull_requests_router,
)
from app.db.session import get_db
from app.api.changes import router as changes_router
from app.api.conflicts import router as conflicts_router
from app.api.git_http import router as git_router
from app.api.repositories import (
    router as repository_router,
)
from app.api.repository_browser import (
    router as repository_browser_router,
)
from app.api.organizations import router as organizations_router
from app.api.social import router as social_router
from app.api.explore import router as explore_router
from app.api.search import router as search_router
from app.api.profiles import router as profiles_router
from app.api.artifacts import router as artifacts_router
from app.api.environments import router as environments_router
from app.api.deployments import router as deployments_router
from app.api.assistant import router as assistant_router
from app.api.audit import router as audit_router, activity_router
from app.api.sso import router as sso_router
from app.api.governance import router as governance_router
from app.api.packages import router as packages_router
from app.api.notifications import router as notifications_router
from app.api.me import router as me_router
from app.api.insights import router as insights_router, global_router as global_insights_router
from app.api.security import router as security_router
from app.api.releases import router as releases_router
from app.api.integrations import router as integrations_router
from app.api.lifecycle import router as lifecycle_router

from app.api.tasks import (
    router as tasks_router,
)
from app.api.agent_reviews import router as agent_reviews_router
from app.api.inline_reviews import router as inline_reviews_router
from app.core.config import settings

from app.services.session_reaper_worker import SessionReaperWorker

reaper_worker = SessionReaperWorker()

from app.mcp.server import mcp_server, get_mcp_routes

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    Path(
        settings.repository_storage_path
    ).mkdir(
        parents=True,
        exist_ok=True,
    )
    
    reaper_worker.start()

    mcp_server.session_manager._has_started = False
    async with mcp_server.session_manager.run():
        yield
    
    reaper_worker.stop()


from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limit import limiter

_AGENT_INTEGRATION_DOCS_PATH = "/docs/agent-integration.md"

_OPENAPI_TAGS = [
    {
        "name": "agent_registration",
        "description": (
            "**Agent Registration (Public)**\n\n"
            "External agents use this to initiate a registration request without credentials. "
            "The human owner must approve the request before a permanent token is issued. "
            "See `/v1/agents/register` to start and `/v1/agents/register/{id}/status` to poll for approval."
        ),
    },
    {
        "name": "agents",
        "description": (
            "**Agent Management and Session Lifecycle**\n\n"
            "Humans manage agents via `POST /v1/agents` (requires Human JWT). "
            "Agents obtain a short-lived AgentSession via `POST /v1/agents/session` (requires permanent agent token). "
            "All agent API and Git operations use the AgentSession token as `Authorization: Bearer sutra_session_...`. "
            "AgentSession expiry: **15 minutes absolute / 120 seconds idle**. "
            "Send heartbeats every 30-60 seconds via `POST /v1/agents/heartbeat`."
        ),
    },
    {
        "name": "agent-sessions",
        "description": (
            "**Agent Session Inspection (Human JWT required)**\n\n"
            "Allows the human owner to list and revoke active sessions for their agents."
        ),
    },
    {
        "name": "agent-protocol",
        "description": (
            "**Agent Protocol Handshake and Capability Discovery**\n\n"
            "External agents SHOULD call `POST /v1/agent-protocol/handshake` immediately after "
            "obtaining an AgentSession to receive the canonical workflow steps and session instructions. "
            "The handshake is authenticated and returns structured JSON describing the full agent lifecycle."
        ),
    },
    {
        "name": "repository-agents",
        "description": (
            "**Repository Agent Access Management (Human JWT required)**\n\n"
            "Grants or revokes an agent's access to a specific repository. "
            "Only the repository owner can call these endpoints. "
            "**An agent cannot grant itself access.** "
            "Supported capabilities: `repository.read`, `repository.write`, `change.create`, "
            "`change.commit`, `change.conflict.read`, `knowledge_graph.read`, `knowledge_graph.write`."
        ),
    },
    {
        "name": "changes",
        "description": (
            "**Change Lifecycle (Human JWT or AgentSession)**\n\n"
            "A Change records an agent's declared intent and the resulting commit. "
            "Agents use `POST /v1/changes/agent` (requires `change.create` capability) and "
            "`POST /v1/changes/{id}/agent-commit` (requires `change.commit` capability). "
            "Recording a commit does NOT approve or finalize the change. Human review is still required."
        ),
    },
    {
        "name": "change-reviews",
        "description": (
            "**Change Review Lifecycle (Human JWT only)**\n\n"
            "Humans request and approve/reject reviews on Changes. "
            "**The requester cannot approve their own review request.** "
            "Agents cannot call approval/rejection endpoints — these require a Human JWT."
        ),
    },
    {
        "name": "pull-requests",
        "description": (
            "**Pull Request Lifecycle (Human JWT or AgentSession)**\n\n"
            "Agents create PRs via `POST /v1/pull-requests/agent` (requires AgentSession and a Change with a `resulting_commit`). "
            "**Agents cannot approve or merge a PR.** Merge requires Human JWT."
        ),
    },
    {
        "name": "git",
        "description": (
            "**Git Smart HTTP Transport**\n\n"
            "Implements Git Smart HTTP for clone, fetch, and push. "
            "Authentication: HTTP Basic Auth with:\n"
            "- **Username**: Agent token prefix (first 16 characters of the permanent `sutra_agent_...` token)\n"
            "- **Password**: Active AgentSession token (`sutra_session_...`)\n\n"
            "Git push requires `repository.write` capability. "
            "Git clone/fetch requires `repository.read` capability. "
            "The session must be active for the entire duration of the Git operation."
        ),
    },
    {
        "name": "authentication",
        "description": (
            "**Human Authentication (Email + Password)**\n\n"
            "Register and login for human users. "
            "Login returns a Human JWT used as `Authorization: Bearer <jwt>` for human-facing endpoints. "
            "This JWT is NOT accepted by agent endpoints or Git HTTP."
        ),
    },
]

app = FastAPI(
    title="SUTRA API",
    version="0.2.0",
    description=(
        "SUTRA - a Git-compatible, policy-enforced source control and engineering platform.\n\n"
        "## Authentication Types\n\n"
        "SUTRA uses two separate authentication systems:\n\n"
        "### Human Authentication\n"
        "Obtain a Human JWT via `POST /v1/auth/login`. Use as `Authorization: Bearer <jwt>`. "
        "Expiry: 60 minutes. Required for: agent management, repository grants, PR review/approval, merge.\n\n"
        "### Agent Authentication\n"
        "1. Exchange permanent agent token (`sutra_agent_...`) for an AgentSession: "
        "`POST /v1/agents/session`\n"
        "2. Use AgentSession token (`sutra_session_...`) as `Authorization: Bearer <session_token>` "
        "for all agent API endpoints.\n"
        "3. Use AgentSession token as the Git HTTP **password** (username = agent token prefix).\n\n"
        "AgentSession expiry: **15 minutes absolute, 120 seconds idle**.\n\n"
        "## Agent Quickstart\n\n"
        "1. Human creates agent via `POST /v1/agents` (JWT required)\n"
        "2. Agent creates session via `POST /v1/agents/session` (permanent token)\n"
        "3. Human grants repo access via `POST /v1/repositories/{owner}/{repo}/agents` (JWT required)\n"
        "4. Agent clones: `git clone https://<token_prefix>:<session_token>@<host>/git/<owner>/<repo>.git`\n"
        "5. Agent pushes, creates Change, records commit, creates PR\n"
        "6. Human reviews and merges\n\n"
        "See `GET /v1/agent-info` for machine-readable workflow metadata.\n"
        "See `POST /v1/agent-protocol/handshake` for full protocol instructions.\n"
        "See `/docs/agent-integration.md` for the complete integration guide."
    ),
    openapi_tags=_OPENAPI_TAGS,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # Content-Security-Policy that allows Next.js frontend, WebSocket/HTTP connections, and tunnel hosts to operate smoothly
    response.headers["Content-Security-Policy"] = "default-src 'self' * 'unsafe-inline' 'unsafe-eval'; script-src 'self' 'unsafe-inline' 'unsafe-eval' *; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: *; connect-src 'self' * ws: wss:;"
    return response


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request: Request, exc: OperationalError):
    import logging
    logging.getLogger("sutra.api").error("Database unavailable", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database temporarily unavailable. Please retry shortly.",
            "code": "DATABASE_UNAVAILABLE",
        },
        headers={"Retry-After": "5"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger("sutra.api").error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.get("/", tags=["discovery"])
def root(request: Request):
    base = settings.get_public_api_url(request)
    return {
        "name": "SUTRA - The Engineering OS",
        "version": "0.2.0",
        "status": "running",
        "greeting": (
            "Welcome to SUTRA! "
            "If you are a Human, authenticate via the web interface. "
            "If you are an Autonomous Agent or Custom Client, call the agent_protocol_handshake_url "
            "after obtaining an AgentSession, or read the agent_integration_docs_url for the full guide."
        ),
        "authentication": {
            "human": {
                "description": "Obtain a Human JWT via POST /v1/auth/login",
                "login_url": f"{base}/v1/auth/login",
                "token_format": "opaque JWT",
                "used_for": "All human-facing API endpoints",
            },
            "agent": {
                "description": "Exchange permanent agent token for short-lived AgentSession",
                "session_url": f"{base}/v1/agents/session",
                "token_format": "sutra_session_...",
                "used_for": "Agent API endpoints and Git HTTP password",
                "expiry_seconds": 900,
                "idle_timeout_seconds": 120,
            },
        },
        "links": {
            "human_login_url": f"{base}/v1/auth/login",
            "agent_registration_url": f"{base}/v1/agents/register",
            "agent_session_url": f"{base}/v1/agents/session",
            "agent_info_url": f"{base}/v1/agent-info",
            "agent_protocol_handshake_url": f"{base}/v1/agent-protocol/handshake",
            "agent_integration_docs_url": f"{base}/docs/agent-integration.md",
            "openapi_documentation_url": f"{base}/docs",
            "health_url": f"{base}/health",
            "ready_url": f"{base}/ready",
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "sutra-api",
    }


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        # 1. DB connectivity
        db.execute(text("SELECT 1"))

        # 2. Storage directory check
        storage_path = Path(settings.repository_storage_path)
        if not storage_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Git storage path unavailable")

        return {
            "status": "ready",
            "database": "connected",
            "storage": "available",
        }
    except Exception as exc:
        from fastapi import HTTPException
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=503, detail="System readiness check failed")


@app.get("/metrics", include_in_schema=False)
def metrics():
    from fastapi.responses import PlainTextResponse
    from app.core.metrics import metrics_collector
    return PlainTextResponse(metrics_collector.get_metrics_formatted())


@app.get(
    "/v1/agent-info",
    tags=["discovery"],
    summary="Agent Lifecycle Metadata",
    description=(
        "Returns machine-readable workflow metadata for external coding agents. "
        "Includes the canonical step sequence, credential formats, capability list, "
        "Git authentication format, and important human permission boundaries. "
        "No authentication required. Does not expose internal infrastructure."
    ),
)
def agent_info(request: Request):
    base = settings.get_public_api_url(request)
    return {
        "sutra_version": "0.2.0",
        "api_base": f"{base}/v1",
        "git_base": f"{base}/git",
        "openapi_docs": f"{base}/docs",
        "agent_integration_guide": f"{base}/docs/agent-integration.md",
        "protocol_handshake": f"{base}/v1/agent-protocol/handshake",
        "credential_types": {
            "human_jwt": {
                "format": "opaque",
                "obtained_via": "POST /v1/auth/login",
                "used_for": "Human-facing API endpoints",
                "header": "Authorization: Bearer <jwt>",
                "expiry_minutes": 60,
            },
            "agent_permanent_token": {
                "format": "sutra_agent_<random>",
                "obtained_via": "POST /v1/agents (human) or registration approval",
                "used_for": "Creating AgentSessions only (POST /v1/agents/session)",
                "never_use_as": "Bearer token for agent API calls or Git password",
                "expiry": "never (until revoked)",
            },
            "agent_session_token": {
                "format": "sutra_session_<random>",
                "obtained_via": "POST /v1/agents/session",
                "used_for": "Agent API endpoints (Authorization: Bearer) and Git HTTP password",
                "header": "Authorization: Bearer sutra_session_<random>",
                "expiry_absolute_minutes": 15,
                "idle_timeout_seconds": 120,
                "extend_via": "POST /v1/agents/heartbeat (send every 30-60s)",
            },
            "temporary_push_token": {
                "format": "sutra_temp_push_<random>",
                "obtained_via": "POST /v1/agents/register (before approval)",
                "used_for": "Single-use Git push during pre-approval registration flow only",
                "single_use": True,
                "expiry_hours": 1,
            },
        },
        "git_authentication": {
            "protocol": "Git Smart HTTP over Basic Auth",
            "clone_url_pattern": "https://github.com/{owner}/{repo}.git",
            "username": "<first 16 characters of permanent agent token, e.g. sutra_agent_AbCd>",
            "password": "<full AgentSession token: sutra_session_...>",
            "note": "Username is the permanent token prefix. Password is the AgentSession token. Do not swap.",
        },
        "capabilities": [
            {"name": "repository.read", "allows": "git clone, git fetch, read API"},
            {"name": "repository.write", "allows": "git push"},
            {"name": "change.create", "allows": "POST /v1/changes/agent"},
            {"name": "change.commit", "allows": "POST /v1/changes/{id}/agent-commit"},
            {"name": "change.conflict.read", "allows": "Read conflict detection API"},
            {"name": "knowledge_graph.read", "allows": "GET /v1/knowledge-graph"},
            {"name": "knowledge_graph.write", "allows": "Modify knowledge graph"},
        ],
        "authorization_rules": [
            "Explicit AgentRepositoryAccess grants are required once any grant exists",
            "Public repository visibility does NOT bypass agent authorization",
            "Same-owner relationship does NOT bypass explicit grants",
            "An agent CANNOT grant itself repository access — only the human owner can",
            "An agent CANNOT approve its own review or PR",
            "Merge is a human-only action",
        ],
        "canonical_workflow": [
            {"step": 1, "actor": "human", "action": "POST /v1/auth/login", "result": "Human JWT"},
            {"step": 2, "actor": "human", "action": "POST /v1/agents", "result": "Permanent agent token (returned once)"},
            {"step": 3, "actor": "human", "action": "POST /v1/repositories/{owner}/{repo}/agents", "result": "Repository access grant"},
            {"step": 4, "actor": "agent", "action": "POST /v1/agents/session", "result": "AgentSession token (15 min TTL)"},
            {"step": 5, "actor": "agent", "action": "POST /v1/agents/heartbeat every 30-60s", "result": "Session kept alive"},
            {"step": 6, "actor": "agent", "action": "git clone (Basic Auth with session token)", "result": "Local repository"},
            {"step": 7, "actor": "agent", "action": "Make code changes and git push", "result": "Commit on remote branch"},
            {"step": 8, "actor": "agent", "action": "POST /v1/changes/agent", "result": "Change record (status: proposed)"},
            {"step": 9, "actor": "agent", "action": "POST /v1/changes/{id}/agent-commit", "result": "Commit evidence recorded (NOT approved)"},
            {"step": 10, "actor": "agent", "action": "POST /v1/changes/{id}/agent-finalize", "result": "Change finalized (review still required)"},
            {"step": 11, "actor": "agent", "action": "POST /v1/pull-requests/agent", "result": "PR created (status: open)"},
            {"step": 12, "actor": "agent", "action": "Notify human that PR is ready", "result": "Human informed"},
            {"step": 13, "actor": "human", "action": "POST /v1/changes/{id}/reviews", "result": "Review requested"},
            {"step": 14, "actor": "different_human", "action": "POST /v1/changes/{id}/reviews/{review_id}/approve", "result": "Review approved (requester != reviewer enforced)"},
            {"step": 15, "actor": "human", "action": "POST /v1/pull-requests/{id}/merge", "result": "PR merged"},
        ],
        "human_must_do": [
            "Approve agent registration requests",
            "Grant repository access to agents",
            "Approve change reviews (and reviewer must differ from requester)",
            "Merge pull requests",
        ],
        "agent_cannot_do": [
            "Grant itself repository access",
            "Approve its own review or PR",
            "Merge a PR",
            "Use an expired or revoked session",
            "Escalate capabilities beyond what is granted",
        ],
        "error_guide": {
            "401": "Session expired or invalid. Create a new AgentSession via POST /v1/agents/session.",
            "403": "Missing capability or repository access. Ask the human owner to grant access.",
            "404": "Resource not found or not accessible. Verify IDs.",
            "409": "Conflict (duplicate, policy block, merge conflict). Check existing state.",
            "429": "Rate limited. Respect Retry-After header.",
            "503": "Security service temporarily unavailable. Back off and retry.",
        },
    }


from app.api.agents import get_agent_context, AgentContextResponse
from app.api.agent_dependencies import get_current_agent_session, get_current_agent
from app.models.agent_session import AgentSession
from app.models.agent import Agent

@app.get(
    "/v1/agent/context",
    response_model=AgentContextResponse,
    tags=["agent-context"],
    summary="Agent Context (Canonical Endpoint)",
    description="Machine-readable canonical context endpoint for autonomous agents.",
)
def get_canonical_agent_context(
    current_session: AgentSession = Depends(get_current_agent_session),
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> AgentContextResponse:
    return get_agent_context(current_session, current_agent, db)


app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(agent_registration_router)
app.include_router(agent_repository_access_router)
app.include_router(agent_protocol_router)
app.include_router(agent_tasks_router)
app.include_router(branch_protection_router)
app.include_router(pull_requests_router)
app.include_router(repository_router)
app.include_router(repository_browser_router)
app.include_router(knowledge_graph_router)
app.include_router(issues_router)
app.include_router(discussions_router)
app.include_router(agent_messages_router)
app.include_router(tasks_router)
app.include_router(changes_router)
app.include_router(change_graph_router)
app.include_router(conflicts_router)
app.include_router(git_router)
app.include_router(change_policy_router)
app.include_router(change_reviews_router)
app.include_router(ci_router)
app.include_router(agent_sessions_router)
app.include_router(organizations_router)
app.include_router(social_router)
app.include_router(explore_router)
app.include_router(search_router)
app.include_router(profiles_router)
app.include_router(artifacts_router)
app.include_router(environments_router)
app.include_router(deployments_router)
app.include_router(assistant_router)
app.include_router(audit_router)
app.include_router(activity_router)
app.include_router(sso_router)
app.include_router(governance_router)
app.include_router(packages_router)
app.include_router(agent_reviews_router)
app.include_router(inline_reviews_router)
app.include_router(notifications_router)
app.include_router(me_router)
app.include_router(insights_router)
app.include_router(global_insights_router)
app.include_router(security_router)
app.include_router(releases_router)
app.include_router(integrations_router)
app.include_router(agent_issues_router)
app.include_router(lifecycle_router)

from app.api.webhooks.github import router as webhooks_router
app.include_router(webhooks_router)

from app.api.oauth import router as oauth_router
app.include_router(oauth_router)

# Mount official MCP Streamable HTTP transport routes (/v1/mcp)
app.router.routes.extend(get_mcp_routes())