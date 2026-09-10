"""Test Suite for SUTRA MCP OAuth 2.1 Discovery and PKCE Token Exchange."""
import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.mcp.server import mcp_server
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.repository_service import RepositoryService


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


@asynccontextmanager
async def run_mcp():
    mcp_server.session_manager._has_started = False
    async with mcp_server.session_manager.run():
        yield


@pytest.fixture
def setup_oauth_environment(db_session):
    now = datetime.now(timezone.utc)
    uid = secrets.token_hex(8)

    # 1. Human owner
    owner = User(
        id=f"user_{uid}",
        username=f"owner_{uid}",
        email=f"owner_{uid}@example.com",
        password_hash=hash_password("password123"),
        email_verified=True,
    )
    db_session.add(owner)

    owner_actor = Actor(
        id=owner.id,
        owner_id=owner.id,
        type="human",
        name=owner.username,
        capabilities="[]",
    )
    db_session.add(owner_actor)

    # 2. Repository
    repo = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"oauth-repo-{uid}",
        description="OAuth test repo",
        visibility="private",
    )

    # 3. Dedicated Agent
    raw_agent_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    agent = Agent(
        id=f"agnt_{uid}",
        owner_id=owner.id,
        name=f"oauth-agent-{uid}",
        token_hash=hash_password(raw_agent_token),
        token_prefix=raw_agent_token[:16],
        status="active",
        is_active=True,
    )
    db_session.add(agent)

    agent_actor = Actor(
        id=agent.id,
        owner_id=owner.id,
        type="agent",
        name=agent.name,
        capabilities=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "change.conflict.read",
            "knowledge_graph.read",
        ]),
    )
    db_session.add(agent_actor)
    db_session.commit()

    # 4. Agent Repository Access
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "change.conflict.read",
            "knowledge_graph.read",
        ]),
        enabled=True,
    )
    db_session.add(access)
    db_session.commit()

    yield {
        "owner": owner,
        "repo": repo,
        "agent": agent,
    }

    # Cleanup
    try:
        db_session.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.id == access.id).delete()
        db_session.commit()
        db_session.query(Actor).filter(Actor.id.in_([owner.id, agent.id])).delete()
        db_session.query(Agent).filter(Agent.id == agent.id).delete()
        db_session.query(Repository).filter(Repository.id == repo.id).delete()
        db_session.query(User).filter(User.id == owner.id).delete()
        db_session.commit()
        repo_dir = (Path(settings.repository_storage_path).resolve() / repo.storage_key).resolve()
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
    except Exception:
        db_session.rollback()


@pytest.mark.asyncio
async def test_oauth_metadata_discovery():
    """Verify RFC 8414 and RFC 9728 metadata endpoints return required MCP parameters."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        # 1. RFC 8414: OAuth Authorization Server Metadata
        as_res = await client.get("/.well-known/oauth-authorization-server")
        assert as_res.status_code == 200
        as_data = as_res.json()
        assert as_data["issuer"] == "http://localhost"
        assert as_data["authorization_endpoint"] == "http://localhost/oauth/authorize"
        assert as_data["token_endpoint"] == "http://localhost/oauth/token"
        assert as_data["revocation_endpoint"] == "http://localhost/oauth/revoke"
        assert as_data["registration_endpoint"] == "http://localhost/oauth/register"
        assert as_data["client_id_metadata_document_supported"] is True
        assert as_data["authorization_response_iss_parameter_supported"] is True
        assert "S256" in as_data["code_challenge_methods_supported"]
        assert "authorization_code" in as_data["grant_types_supported"]

        # 2. RFC 9728: Protected Resource Metadata
        pr_res = await client.get("/.well-known/oauth-protected-resource")
        assert pr_res.status_code == 200
        pr_data = pr_res.json()
        assert pr_data["resource"] == "http://localhost/v1/mcp"
        assert pr_data["authorization_servers"] == ["http://localhost"]

        # 3. RFC 7591: Dynamic Client Registration fallback
        reg_res = await client.post(
            "/oauth/register",
            json={
                "client_name": "Test IDE Client",
                "redirect_uris": ["https://ide.local/oauth/callback"],
            },
        )
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        assert reg_data["client_id"].startswith("sutra_client_")
        assert "authorization_code" in reg_data["grant_types"]

        # 4. RFC 7009: Token Revocation endpoint
        rev_res = await client.post(
            "/oauth/revoke",
            data={"token": "sutra_mcp_at_fake_revocation_test", "token_type_hint": "access_token"},
        )
        assert rev_res.status_code == 200
        assert rev_res.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_oauth_pkce_authorization_and_mcp_call(setup_oauth_environment):
    """
    Test full OAuth 2.1 PKCE Flow:
    1. Generate PKCE code_challenge / verifier
    2. Request /oauth/authorize -> receives code
    3. Exchange code with wrong verifier -> 400
    4. Exchange code with correct verifier -> 200, receives sutra_mcp_at_...
    5. Execute MCP tool call (sutra_get_context) with OAuth token over Streamable HTTP -> 200
    6. Refresh token grant -> 200, receives new access token
    """
    env = setup_oauth_environment

    # 1. Generate PKCE verifier and challenge
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    redirect_uri = "https://client.local/callback"
    state = secrets.token_hex(16)

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            # 2. Authorize
            auth_res = await client.get(
                "/oauth/authorize",
                params={
                    "client_id": "cursor-ide",
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                    "state": state,
                    "scope": "sutra:agent",
                    "agent_id": env["agent"].id,
                },
                follow_redirects=False,
            )
            assert auth_res.status_code == 302
            loc = auth_res.headers.get("location")
            assert loc.startswith(redirect_uri)
            parsed = urlparse(loc)
            params = parse_qs(parsed.query)
            code = params["code"][0]
            assert params["state"][0] == state

            # 3. Invalid PKCE verifier fails
            fail_res = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": "cursor-ide",
                    "code_verifier": "wrong-verifier",
                },
            )
            assert fail_res.status_code == 400

            # 4. Authorize again to get a fresh code
            auth_res2 = await client.get(
                "/oauth/authorize",
                params={
                    "client_id": "cursor-ide",
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                    "state": state,
                    "scope": "sutra:agent",
                    "agent_id": env["agent"].id,
                },
                follow_redirects=False,
            )
            code2 = parse_qs(urlparse(auth_res2.headers.get("location")).query)["code"][0]

            # Exchange code with valid verifier
            token_res = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code2,
                    "redirect_uri": redirect_uri,
                    "client_id": "cursor-ide",
                    "code_verifier": code_verifier,
                },
            )
            assert token_res.status_code == 200
            token_data = token_res.json()
            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]
            assert access_token.startswith("sutra_mcp_at_")
            assert refresh_token.startswith("sutra_mcp_rt_")
            assert token_data["token_type"] == "Bearer"
            assert token_data["expires_in"] == 900

            # 5. Call MCP Streamable HTTP tool using the OAuth access token
            init_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "oauth-client", "version": "1"}},
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200
            session_id = init_res.headers.get("mcp-session-id")

            tool_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "sutra_get_context", "arguments": {}},
                },
                headers={
                    "mcp-session-id": session_id,
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert tool_res.status_code == 200
            lines = [line.strip() for line in tool_res.text.splitlines() if line.startswith("data: ")]
            payload = json.loads(lines[0][len("data: "):])
            result = payload["result"]
            sc = result.get("structuredContent")
            ctx_data = sc["result"] if isinstance(sc, dict) and "result" in sc else sc
            assert ctx_data["identity"]["agent_id"] == env["agent"].id
            assert ctx_data["session"]["session_id"] is not None

            # 6. Refresh token grant
            rf_res = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            assert rf_res.status_code == 200
            new_token_data = rf_res.json()
            assert new_token_data["access_token"].startswith("sutra_mcp_at_")
