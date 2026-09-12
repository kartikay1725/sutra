"""SUTRA MCP Server Instance and Transport Configuration.

Provides the official MCP Python SDK Streamable HTTP server configured for
production integration into FastAPI with HTTP-layer Bearer authentication challenge.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import List

from pydantic import AnyHttpUrl
from sqlalchemy import select
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.routing import BaseRoute, Route
from starlette.types import Receive, Scope, Send

from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import CANONICAL_PRODUCTION_API_URL, settings
from app.core.redis_service import redis_service
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.mcp.tools import register_sutra_tools

logger = logging.getLogger("sutra.mcp.server")

# 1. Instantiate the official MCP Server
mcp_server = MCPServer(
    name="sutra",
    instructions=(
        "SUTRA is an AI-native engineering control plane governing repository changes across the full lifecycle: "
        "Task -> Change -> Commit -> PR -> CI -> Governance -> Human Approval -> Merge.\n\n"
        "ENGINEERING BOUNDARY:\n"
        "- Terminal/local tools are appropriate for: reading files, editing files, running tests, "
        "running local builds, and git inspection (status, diff, log).\n"
        "- SUTRA MCP tools MUST be used for governed repository operations: starting tasks, declaring changes, "
        "creating and pushing commits, opening Pull Requests, lifecycle tracking, governance evaluations, and merge requests.\n"
        "- SUTRA does not replace GitHub or local git inspection; it governs repository changes and code submission "
        "with cryptographic provenance so commits and PRs are verifiable.\n\n"
        "INTENT -> TOOL MAPPING (Natural Engineering Language):\n"
        "- 'start working on this' / 'fix this bug' / 'implement feature' / 'new coding request' -> sutra_start_task "
        "(Creates task automatically; do NOT ask the user for a Task ID!)\n"
        "- 'who am I' / 'check permissions' / 'check session' -> sutra_get_context\n"
        "- 'search codebase architecture' / 'find symbol' / 'explore dependencies' -> sutra_search_knowledge\n"
        "- 'track this change' / 'start code change' / 'allocate feature branch' -> sutra_declare_change\n"
        "- 'commit this' / 'push this change' / 'create a commit' / 'push commit' -> sutra_push_commit "
        "(Use this instead of terminal git commit/git push for governed work)\n"
        "- 'open a PR' / 'create a pull request' / 'submit PR for review' -> sutra_open_pull_request "
        "(Use this instead of gh pr create/direct PR creation)\n"
        "- 'what's the status?' / 'where is my PR?' / 'what's blocking?' -> sutra_get_status\n"
        "- 'can this merge?' / 'why can't this merge?' / 'is CI passing?' -> sutra_get_governance\n"
        "- 'request merge' / 'ready to merge' / 'handover for merge' -> sutra_request_merge "
        "(Human approval is always required; agents cannot merge directly)\n"
        "- 'who wrote this commit?' / 'check commit provenance' -> sutra_get_provenance\n"
        "- 'file a bug' / 'create an issue' / 'report technical debt' -> sutra_create_issue\n"
        "- 'finish the task' / 'mark task complete' / 'summarize validation' -> sutra_complete_task\n\n"
        "CANONICAL WORKFLOW:\n"
        "1. sutra_start_task: Claim or auto-create the engineering task from user request.\n"
        "2. sutra_declare_change: Allocate the git feature branch and establish tracked change record.\n"
        "3. sutra_push_commit: Submit file modifications and commit message with SUTRA cryptographic provenance.\n"
        "4. sutra_open_pull_request: Open the linked GitHub PR and trigger CI/governance evaluation.\n"
        "5. sutra_get_governance / sutra_get_status: Check CI checks and merge readiness.\n"
        "6. sutra_complete_task: Record implementation and test validation summary.\n\n"
        "LEGACY TOOL NOTE:\n"
        "- sutra_submit_change is deprecated for new work. Always use the canonical 3-step pipeline: "
        "sutra_declare_change -> sutra_push_commit -> sutra_open_pull_request."
    ),
    version="0.4.0",
)

# 2. Register curated SUTRA tools
register_sutra_tools(mcp_server)

# 3. Configure transport security settings
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=["*"],
    allowed_origins=["*"],
)

# 4. Generate the official Streamable HTTP Starlette application
_streamable_app = mcp_server.streamable_http_app(
    streamable_http_path="/v1/mcp",
    transport_security=_transport_security,
)


class SutraTokenVerifier:
    """Official MCP TokenVerifier for SUTRA Bearer tokens."""

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None

        canonical_resource = f"{CANONICAL_PRODUCTION_API_URL}/v1/mcp"

        # 1. OAuth Access Token: sutra_mcp_at_...
        if token.startswith("sutra_mcp_at_"):
            token_prefix = token[:32]
            try:
                cached = redis_service.get(f"mcp_oauth:{token_prefix}")
                if cached and isinstance(cached, dict):
                    agent_id = cached.get("agent_id")
                    if agent_id:
                        with SessionLocal() as db:
                            agent = db.scalar(
                                select(Agent).where(
                                    Agent.id == agent_id,
                                    Agent.is_active.is_(True),
                                    Agent.status == "active",
                                )
                            )
                            if agent:
                                return AccessToken(
                                    token=token,
                                    client_id=cached.get("client_id", agent_id),
                                    scopes=["sutra:agent"],
                                    resource=canonical_resource,
                                )
            except Exception as e:
                logger.warning(f"Error verifying SUTRA OAuth token in TokenVerifier: {e}")
            return None

        # 2. Permanent Agent Token: sutra_agent_...
        if token.startswith("sutra_agent_"):
            try:
                from app.api.agent_dependencies import authenticate_agent_token
                with SessionLocal() as db:
                    agent = authenticate_agent_token(token, db)
                    if agent:
                        return AccessToken(
                            token=token,
                            client_id=agent.id,
                            scopes=["sutra:agent"],
                            resource=canonical_resource,
                        )
            except Exception as e:
                logger.warning(f"Error verifying SUTRA Agent token in TokenVerifier: {e}")
            return None

        # 3. AgentSession Token: sutra_session_...
        if token.startswith("sutra_session_"):
            try:
                from app.api.agent_dependencies import validate_agent_session_token
                with SessionLocal() as db:
                    sess = validate_agent_session_token(token, db)
                    if sess:
                        return AccessToken(
                            token=token,
                            client_id=sess.agent_id,
                            scopes=["sutra:agent"],
                            resource=canonical_resource,
                        )
            except Exception as e:
                logger.warning(f"Error verifying SUTRA AgentSession token in TokenVerifier: {e}")
            return None

        return None


class DynamicResourceMetadataRequireAuth(RequireAuthMiddleware):
    """
    Subclasses official RequireAuthMiddleware to dynamically resolve the canonical
    resource_metadata URL for WWW-Authenticate challenges according to the host.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            host_header = headers.get(b"host", b"").decode("latin-1")
            scheme = "https" if scope.get("scheme") == "https" or headers.get(b"x-forwarded-proto") == b"https" else "http"
            if "api.sutra.sudarshanai.com" in host_header or not host_header:
                self.resource_metadata_url = AnyHttpUrl(f"{CANONICAL_PRODUCTION_API_URL}/.well-known/oauth-protected-resource")
            else:
                self.resource_metadata_url = AnyHttpUrl(f"{scheme}://{host_header}/.well-known/oauth-protected-resource")
        await super().__call__(scope, receive, send)


sutra_token_verifier = SutraTokenVerifier()
_auth_backend = BearerAuthBackend(sutra_token_verifier)
_raw_endpoint = _streamable_app.routes[0].endpoint
_require_auth_app = DynamicResourceMetadataRequireAuth(
    _raw_endpoint,
    required_scopes=["sutra:agent"],
    resource_metadata_url=AnyHttpUrl(f"{CANONICAL_PRODUCTION_API_URL}/.well-known/oauth-protected-resource"),
)
_protected_endpoint = AuthenticationMiddleware(_require_auth_app, backend=_auth_backend)
if not hasattr(_protected_endpoint, "__name__"):
    _protected_endpoint.__name__ = "streamable_http_protected_endpoint"


def get_mcp_routes() -> List[BaseRoute]:

    """
    Returns the Starlette routes configured for Streamable HTTP transport
    wrapped with official MCP SDK HTTP-layer Bearer authentication challenge.
    """
    return [
        Route("/v1/mcp", endpoint=_protected_endpoint),
        Route("/v1/mcp/", endpoint=_protected_endpoint),
    ]

