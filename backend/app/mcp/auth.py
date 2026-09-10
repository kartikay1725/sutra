"""MCP Authentication and AgentSession Adapter.

Maps incoming MCP transport requests (via Context headers) to authoritative
SUTRA Agent and AgentSession database records without creating any parallel
session model.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import (
    authenticate_agent_token,
    create_agent_session,
    validate_agent_session_token,
)
from app.core.redis_service import redis_service
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from mcp.server.mcpserver import Context

logger = logging.getLogger("sutra.mcp.auth")


class MCPAuthError(Exception):
    """Raised when MCP tool execution fails authentication or session binding."""

    def __init__(self, message: str, code: int = 401):
        super().__init__(message)
        self.message = message
        self.code = code


def extract_bearer_token(ctx: Context) -> str:
    """Extract Bearer token from MCP Context headers."""
    if not ctx or not hasattr(ctx, "headers") or not ctx.headers:
        raise MCPAuthError("Authentication required: no request headers provided in MCP context", code=401)

    headers = {k.lower(): v for k, v in ctx.headers.items()}
    auth_header = headers.get("authorization")

    if not auth_header:
        raise MCPAuthError(
            "Authentication required: missing 'Authorization: Bearer <token>' header. "
            "Connect SUTRA using your agent token or OAuth access token.",
            code=401,
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise MCPAuthError("Authentication required: header must follow 'Bearer <token>' format", code=401)

    return token.strip()


def resolve_mcp_agent_session(ctx: Context, db: Session) -> Tuple[AgentSession, Agent]:
    """
    Resolve authoritative SUTRA AgentSession and Agent from MCP context.

    Supports:
    1. AgentSession tokens: `sutra_session_...` (primary short-lived session)
    2. Permanent Agent tokens: `sutra_agent_...` (automatically acquires a session)
    3. OAuth Access tokens: `sutra_mcp_at_...` (maps to agent and active session)
    """
    token = extract_bearer_token(ctx)

    # 1. Direct AgentSession token
    if token.startswith("sutra_session_"):
        try:
            session = validate_agent_session_token(token, db)
        except HTTPException as exc:
            raise MCPAuthError(exc.detail, code=exc.status_code) from exc

        agent = db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if not agent:
            raise MCPAuthError("Agent is inactive or revoked", code=401)

        return session, agent

    # 2. Permanent Agent Token (Auto-exchange for AgentSession)
    if token.startswith("sutra_agent_"):
        try:
            agent = authenticate_agent_token(token, db)
            session, _ = create_agent_session(agent, db)
            return session, agent
        except HTTPException as exc:
            raise MCPAuthError(exc.detail, code=exc.status_code) from exc

    # 3. OAuth Access Token: sutra_mcp_at_...
    if token.startswith("sutra_mcp_at_"):
        token_prefix = token[:32]
        cached_data = None
        try:
            cached_data = redis_service.get(f"mcp_oauth:{token_prefix}")
        except Exception as e:
            logger.warning(f"Redis lookup error for MCP OAuth token: {e}")

        if not cached_data or not isinstance(cached_data, dict):
            raise MCPAuthError("Invalid or expired SUTRA MCP OAuth access token", code=401)

        agent_id = cached_data.get("agent_id")
        agent = db.scalar(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if not agent:
            raise MCPAuthError("Agent associated with token is inactive or revoked", code=401)

        # Check for existing active session or create new one
        now = datetime.now(timezone.utc)
        active_session = db.scalar(
            select(AgentSession).where(
                AgentSession.agent_id == agent.id,
                AgentSession.status == "active",
                AgentSession.expires_at > now,
                AgentSession.revoked_at.is_(None),
            ).order_by(AgentSession.created_at.desc())
        )

        if active_session:
            active_session.last_seen_at = now
            agent.last_used_at = now
            db.commit()
            return active_session, agent

        session, _ = create_agent_session(agent, db)
        return session, agent

    raise MCPAuthError(
        "Invalid token format. SUTRA expects 'sutra_session_...', 'sutra_agent_...', or 'sutra_mcp_at_...'",
        code=401,
    )
