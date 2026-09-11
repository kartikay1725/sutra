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
        "SUTRA is an AI-native engineering control plane that coordinates, audits, "
        "and governs autonomous coding agents. Code cannot be merged into production "
        "branches without satisfying SUTRA's 4-pillar governance policy and human approval. "
        "Always begin your interaction by calling sutra_get_context."
    ),
    version="0.4.0",
)

# 2. Register the 8 curated agent tools
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

