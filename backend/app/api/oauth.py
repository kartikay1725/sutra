"""OAuth 2.1 Authorization Server & Protected Resource Metadata Endpoints.

Implements RFC 8414 (OAuth 2.0 Authorization Server Metadata) and
RFC 9728 (OAuth 2.0 Protected Resource Metadata) for MCP clients (Cursor,
Claude Desktop, Windsurf, CLI), along with PKCE authorization code exchange.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import logging
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import create_agent_session
from app.api.dependencies import get_current_user_optional
from app.core.config import settings
from app.core.redis_service import redis_service
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.user import User

logger = logging.getLogger("sutra.oauth")

router = APIRouter(tags=["oauth"])


def verify_code_challenge(verifier: str, challenge: str, method: str = "S256") -> bool:
    """Verify PKCE code_verifier against stored code_challenge."""
    if method == "S256":
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return secrets.compare_digest(computed, challenge)
    elif method in ("plain", ""):
        return secrets.compare_digest(verifier, challenge)
    return False


# =========================================================================
# RFC 8414 & RFC 9728 METADATA DISCOVERY
# =========================================================================

@router.get("/.well-known/oauth-authorization-server")
def get_oauth_authorization_server_metadata(request: Request) -> Dict[str, Any]:
    """RFC 8414: OAuth 2.0 Authorization Server Metadata."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "revocation_endpoint": f"{base_url}/oauth/revoke",
        "registration_endpoint": f"{base_url}/oauth/register",
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
        "revocation_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["sutra:agent", "repo:read", "repo:write"],
        "service_documentation": f"{base_url}/docs",
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
    }


@router.get("/.well-known/oauth-protected-resource")
@router.get("/v1/mcp/.well-known/oauth-protected-resource")
def get_oauth_protected_resource_metadata(request: Request) -> Dict[str, Any]:
    """RFC 9728: OAuth 2.0 Protected Resource Metadata."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "resource": f"{base_url}/v1/mcp",
        "authorization_servers": [base_url],
        "scopes_supported": ["sutra:agent"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{base_url}/docs",
    }


# =========================================================================
# RFC 7591 DYNAMIC CLIENT REGISTRATION (BACKWARD COMPATIBLE FALLBACK)
# =========================================================================

@router.post("/oauth/register")
async def register_client_endpoint(request: Request) -> Dict[str, Any]:
    """RFC 7591 Dynamic Client Registration endpoint (fallback when CIMD is not used)."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    client_id = f"sutra_client_{secrets.token_urlsafe(16)}"
    redirect_uris = data.get("redirect_uris", [])
    client_name = data.get("client_name", "MCP Coding Client")

    client_info = {
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": data.get("token_endpoint_auth_method", "none"),
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    try:
        redis_service.set(f"oauth_client:{client_id}", client_info, ex=86400 * 90)
    except Exception as e:
        logger.warning(f"Failed to cache registered client: {e}")

    return client_info


# =========================================================================
# OAUTH AUTHORIZATION FLOW (PKCE)
# =========================================================================

class AuthorizeRequest(BaseModel):
    client_id: str
    redirect_uri: str
    response_type: str = "code"
    code_challenge: str
    code_challenge_method: str = "S256"
    state: Optional[str] = None
    scope: str = "sutra:agent"
    agent_id: Optional[str] = None
    resource: Optional[str] = None


@router.get("/oauth/authorize")
@router.post("/oauth/authorize")
def authorize_endpoint(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query("code"),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query("S256"),
    state: Optional[str] = Query(None),
    scope: str = Query("sutra:agent"),
    agent_id: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    OAuth 2.1 PKCE Authorize Endpoint.
    Initiated by MCP clients to request delegated access.
    Supports both CIMD (HTTPS URL client_id) and registered clients.
    """
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported response_type. Only 'code' is supported.",
        )

    if code_challenge_method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported code_challenge_method. Only 'S256' is permitted under OAuth 2.1.",
        )

    # Validate redirect_uri format
    if not redirect_uri.startswith("http://") and not redirect_uri.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri. Must be an HTTP or HTTPS URI.",
        )

    # Resolve active agent
    selected_agent: Optional[Agent] = None
    if agent_id:
        selected_agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.is_active.is_(True)))

    if not selected_agent and current_user:
        # Pick or create a dedicated MCP agent for this user
        selected_agent = db.scalar(
            select(Agent).where(
                Agent.owner_id == current_user.id,
                Agent.is_active.is_(True),
            )
        )
        if not selected_agent:
            raw_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
            selected_agent = Agent(
                owner_id=current_user.id,
                name="MCP Coding Agent",
                description="Auto-provisioned agent for Model Context Protocol integration",
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                token_prefix=raw_token[:16],
                status="active",
                is_active=True,
            )
            db.add(selected_agent)
            db.flush()

            actor = Actor(
                id=selected_agent.id,
                owner_id=current_user.id,
                type="agent",
                name=selected_agent.name,
                capabilities=json.dumps([
                    "repository.read",
                    "repository.write",
                    "change.create",
                    "change.commit",
                    "change.conflict.read",
                    "knowledge_graph.read",
                ]),
            )
            db.add(actor)
            db.commit()
            db.refresh(selected_agent)

    # Issue authorization code
    code = f"sutra_auth_code_{secrets.token_urlsafe(32)}"
    code_data = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "scope": scope,
        "resource": resource,
        "agent_id": selected_agent.id if selected_agent else None,
        "user_id": current_user.id if current_user else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        redis_service.set(f"oauth_code:{code}", code_data, ex=600)
    except Exception as e:
        logger.warning(f"Failed to store auth code in Redis: {e}")

    # Build redirect URL with RFC 9207 iss parameter
    base_url = str(request.base_url).rstrip("/")
    params = {"code": code, "iss": base_url}
    if state:
        params["state"] = state

    target_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(params)}"
    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)


# =========================================================================
# TOKEN EXCHANGE (AUTHORIZATION CODE & REFRESH TOKEN)
# =========================================================================

class TokenRequest(BaseModel):
    grant_type: str
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    client_id: Optional[str] = None
    code_verifier: Optional[str] = None
    refresh_token: Optional[str] = None


@router.post("/oauth/token")
async def token_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    OAuth 2.1 Token Exchange Endpoint.
    Exchanges authorization code for an authoritative SUTRA MCP Access Token.
    """
    # Accept both JSON and application/x-www-form-urlencoded
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    grant_type = data.get("grant_type")

    # 1. Authorization Code Grant
    if grant_type == "authorization_code":
        code = data.get("code")
        code_verifier = data.get("code_verifier")
        req_client_id = data.get("client_id")
        req_redirect_uri = data.get("redirect_uri")

        if not code or not code_verifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'code' or 'code_verifier' in request",
            )

        cached_code = None
        try:
            cached_code = redis_service.get(f"oauth_code:{code}")
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")

        if not cached_code or not isinstance(cached_code, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired authorization code",
            )

        # Enforce client_id consistency if provided
        if req_client_id and req_client_id != cached_code.get("client_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client ID mismatch for authorization code",
            )

        # Enforce redirect_uri consistency if provided
        if req_redirect_uri and req_redirect_uri != cached_code.get("redirect_uri"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="redirect_uri mismatch for authorization code",
            )

        # Verify PKCE
        stored_challenge = cached_code.get("code_challenge", "")
        stored_method = cached_code.get("code_challenge_method", "S256")
        if not verify_code_challenge(code_verifier, stored_challenge, stored_method):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PKCE code_verifier verification failed",
            )

        # Invalidate code immediately (single use)
        try:
            redis_service.delete(f"oauth_code:{code}")
        except Exception:
            pass

        # Resolve agent
        agent_id = cached_code.get("agent_id")
        agent = None
        if agent_id:
            agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.is_active.is_(True)))

        if not agent:
            agent = db.scalar(select(Agent).where(Agent.is_active.is_(True)))
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No active agent associated with authorization",
                )

        # Create authoritative SUTRA AgentSession
        session, raw_session_token = create_agent_session(agent, db)

        # Generate OAuth Access Token and Refresh Token
        access_token = f"sutra_mcp_at_{secrets.token_urlsafe(32)}"
        refresh_token = f"sutra_mcp_rt_{secrets.token_urlsafe(32)}"

        # Cache token binding in Redis
        token_prefix = access_token[:32]
        token_data = {
            "agent_id": agent.id,
            "session_id": session.id,
            "raw_session_token": raw_session_token,
            "scope": cached_code.get("scope", "sutra:agent"),
            "resource": cached_code.get("resource"),
            "client_id": cached_code.get("client_id"),
        }
        rt_data = {
            "agent_id": agent.id,
            "scope": cached_code.get("scope", "sutra:agent"),
            "resource": cached_code.get("resource"),
            "client_id": cached_code.get("client_id"),
        }

        try:
            redis_service.set(f"mcp_oauth:{token_prefix}", token_data, ex=900)
            redis_service.set(f"mcp_oauth_rt:{refresh_token}", rt_data, ex=86400 * 30)
        except Exception as e:
            logger.warning(f"Failed to cache OAuth token in Redis: {e}")

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "refresh_token": refresh_token,
            "scope": cached_code.get("scope", "sutra:agent"),
        }

    # 2. Refresh Token Grant
    elif grant_type == "refresh_token":
        rt = data.get("refresh_token")
        if not rt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'refresh_token' parameter",
            )

        rt_data = None
        try:
            rt_data = redis_service.get(f"mcp_oauth_rt:{rt}")
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")

        if not rt_data or not isinstance(rt_data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired refresh token",
            )

        agent_id = rt_data.get("agent_id")
        agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.is_active.is_(True)))
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent is inactive or deleted",
            )

        session, raw_session_token = create_agent_session(agent, db)
        access_token = f"sutra_mcp_at_{secrets.token_urlsafe(32)}"
        token_prefix = access_token[:32]
        token_data = {
            "agent_id": agent.id,
            "session_id": session.id,
            "raw_session_token": raw_session_token,
            "scope": rt_data.get("scope", "sutra:agent"),
            "resource": rt_data.get("resource"),
            "client_id": rt_data.get("client_id"),
        }

        try:
            redis_service.set(f"mcp_oauth:{token_prefix}", token_data, ex=900)
        except Exception as e:
            logger.warning(f"Failed to cache OAuth token in Redis: {e}")

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "refresh_token": rt,
            "scope": rt_data.get("scope", "sutra:agent"),
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type '{grant_type}'",
        )


# =========================================================================
# RFC 7009 TOKEN REVOCATION ENDPOINT
# =========================================================================

@router.post("/oauth/revoke")
async def revoke_token_endpoint(request: Request) -> Dict[str, Any]:
    """RFC 7009 OAuth 2.0 Token Revocation."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    token = data.get("token")
    if token:
        token_type_hint = data.get("token_type_hint")
        try:
            if token.startswith("sutra_mcp_at_") or token_type_hint == "access_token":
                redis_service.delete(f"mcp_oauth:{token[:32]}")
            if token.startswith("sutra_mcp_rt_") or token_type_hint == "refresh_token":
                redis_service.delete(f"mcp_oauth_rt:{token}")
        except Exception as e:
            logger.warning(f"Token revocation error: {e}")

    # RFC 7009 requires returning 200 OK regardless of whether the token existed
    return {"status": "revoked"}
