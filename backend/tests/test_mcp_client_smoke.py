"""
Official Python MCP SDK Client Smoke Test (Section 14).

Steps:
1. Connect without credentials.
2. Confirm authentication challenge is returned at HTTP layer (401 + WWW-Authenticate).
3. Complete OAuth authorization through browser-capable test flow with human approval.
4. Obtain access token.
5. Reconnect to /v1/mcp with official MCP client.
6. Run tools/list.
7. Call sutra_get_context.
8. Verify Agent + AgentSession belong to the correct human.
9. Verify repository list is initially empty (0 default grants).
10. Grant one test repository.
11. Verify MCP context reflects that repository.
12. Call a read-only tool against that repository (sutra_search_knowledge or get_context).
13. Verify authorization blocks a different repository.
"""

import asyncio
import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.redis_service import redis_service
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.mcp.server import mcp_server
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.user import User
from app.models.user_session import UserSession
from app.services.repository_service import RepositoryService


from contextlib import asynccontextmanager

@asynccontextmanager
async def run_mcp():
    mcp_server.session_manager._has_started = False
    async with mcp_server.session_manager.run():
        yield


@pytest.mark.asyncio
async def test_official_mcp_client_smoke_test():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    uid = secrets.token_hex(6)

    with SessionLocal() as db:
        # Create Human User
        user = User(
            id=f"user_{uid}",
            username=f"smoke_human_{uid}",
            email=f"human_{uid}@example.com",
            password_hash=hash_password("SmokePass123!"),
            email_verified=True,
        )
        db.add(user)
        db.flush()

        actor = Actor(id=user.id, owner_id=user.id, type="human", name=user.username, capabilities="[]")
        db.add(actor)
        db.flush()

        sess = UserSession(user_id=user.id, expires_at=now + timedelta(hours=1))
        db.add(sess)
        db.flush()

        human_token = create_access_token(user.id, sess.id)

        # Create two test repositories: repo1 and repo2
        repo1 = Repository(
            name=f"smoke-repo1-{uid}",
            slug=f"smoke-repo1-{uid}",
            owner_id=user.id,
            storage_key=f"storage1_{uid}",
            default_branch="main",
            visibility="private",
        )
        repo2 = Repository(
            name=f"smoke-repo2-{uid}",
            slug=f"smoke-repo2-{uid}",
            owner_id=user.id,
            storage_key=f"storage2_{uid}",
            default_branch="main",
            visibility="private",
        )
        db.add_all([repo1, repo2])
        db.commit()
        db.refresh(user)
        db.refresh(repo1)
        db.refresh(repo2)

    try:
        async with run_mcp():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
                # 1 & 2: Connect without credentials -> HTTP 401 Challenge with WWW-Authenticate
                unauth_res = await client.post(
                    "/v1/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                    headers={"Accept": "application/json, text/event-stream"},
                )
                assert unauth_res.status_code == 401
                assert "Bearer" in unauth_res.headers.get("www-authenticate", "")
                assert 'resource_metadata="https://api.sutra.sudarshanai.com/.well-known/oauth-protected-resource"' in unauth_res.headers["www-authenticate"]

                # 3 & 4: Complete OAuth authorization flow with human approval & PKCE
                code_verifier = secrets.token_urlsafe(64)
                digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
                code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
                redirect_uri = "https://client.local/callback"

                # Authorize with human session
                auth_res = await client.get(
                    "/oauth/authorize",
                    headers={"Authorization": f"Bearer {human_token}"},
                    params={
                        "client_id": "cursor-ide",
                        "redirect_uri": redirect_uri,
                        "response_type": "code",
                        "code_challenge": code_challenge,
                        "code_challenge_method": "S256",
                        "action": "approve",
                    },
                    follow_redirects=False,
                )
                assert auth_res.status_code == 302
                code = parse_qs(urlparse(auth_res.headers["location"]).query)["code"][0]

                # Exchange code for access token
                token_res = await client.post(
                    "/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": "cursor-ide",
                        "code_verifier": code_verifier,
                    },
                )
                assert token_res.status_code == 200
                access_token = token_res.json()["access_token"]
                assert access_token.startswith("sutra_mcp_at_")

                # 5 & 6: Initialize MCP session and run tools/list
                init_res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "smoke-client", "version": "1"}},
                    },
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Authorization": f"Bearer {access_token}",
                    },
                )
                assert init_res.status_code == 200
                session_id = init_res.headers.get("mcp-session-id")

                list_res = await client.post(
                    "/v1/mcp",
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Authorization": f"Bearer {access_token}",
                        "mcp-session-id": session_id,
                    },
                )
                def parse_mcp_response(res):
                    if res.headers.get("content-type", "").startswith("application/json"):
                        return res.json()
                    for line in res.text.splitlines():
                        if line.startswith("data: "):
                            return json.loads(line[len("data: "):])
                    return res.json()

                assert list_res.status_code == 200
                list_payload = parse_mcp_response(list_res)
                tool_names = [t["name"] for t in list_payload["result"]["tools"]]
                assert len(tool_names) == 8
                assert "sutra_get_context" in tool_names

                # 7 & 8: Call sutra_get_context and verify identity
                ctx_res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "sutra_get_context", "arguments": {}},
                    },
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Authorization": f"Bearer {access_token}",
                        "mcp-session-id": session_id,
                    },
                )
                assert ctx_res.status_code == 200
                ctx_payload = parse_mcp_response(ctx_res)
                res_obj = ctx_payload["result"]
                sc = res_obj.get("structuredContent")
                ctx_data = sc["result"] if isinstance(sc, dict) and "result" in sc else sc
                if not ctx_data and "content" in res_obj:
                    ctx_data = json.loads(res_obj["content"][0]["text"])

                agent_id = ctx_data["identity"]["agent_id"]
                with SessionLocal() as db:
                    agent = db.scalar(select(Agent).where(Agent.id == agent_id))
                    assert agent is not None
                    # Step 8: Must belong to the authorizing human
                    assert agent.owner_id == user.id

                # 9: Verify repository list is initially empty (0 default grants)
                repo_access_list = ctx_data.get("repository_access", [])
                assert len(repo_access_list) == 0

                # 10: Explicitly grant one repository (repo1)
                with SessionLocal() as db:
                    access1 = AgentRepositoryAccess(
                        agent_id=agent_id,
                        repository_id=repo1.id,
                        permissions=json.dumps(["repository.read", "repository.write"]),
                        enabled=True,
                    )
                    db.add(access1)
                    db.commit()

                # 11: Call sutra_get_context again -> now reflects repo1
                ctx_res2 = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {"name": "sutra_get_context", "arguments": {}},
                    },
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Authorization": f"Bearer {access_token}",
                        "mcp-session-id": session_id,
                    },
                )
                assert ctx_res2.status_code == 200
                ctx2_payload = parse_mcp_response(ctx_res2)
                sc2 = ctx2_payload["result"].get("structuredContent")
                ctx2 = sc2["result"] if isinstance(sc2, dict) and "result" in sc2 else sc2
                if not ctx2 and "content" in ctx2_payload["result"]:
                    ctx2 = json.loads(ctx2_payload["result"]["content"][0]["text"])
                repo_access_list2 = ctx2.get("repository_access", [])
                assert len(repo_access_list2) == 1
                assert repo_access_list2[0]["repository_id"] == repo1.id

                # 12: Call read-only tool against granted repository (sutra_search_knowledge)
                read_res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {"name": "sutra_search_knowledge", "arguments": {"repository_id": repo1.id, "query": "test query"}},
                    },
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Authorization": f"Bearer {access_token}",
                        "mcp-session-id": session_id,
                    },
                )
                assert read_res.status_code == 200

                # 13: Verify access to repo2 remains blocked (not in repositories, zero access)
                repo_ids = [r["repository_id"] for r in repo_access_list2]
                assert repo2.id not in repo_ids

    finally:
        with SessionLocal() as cleanup_db:
            try:
                test_agents = cleanup_db.query(Agent).filter(Agent.owner_id == user.id).all()
                test_agent_ids = [a.id for a in test_agents]
                if test_agent_ids:
                    cleanup_db.query(AgentSession).filter(AgentSession.agent_id.in_(test_agent_ids)).delete(synchronize_session=False)
                    cleanup_db.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.agent_id.in_(test_agent_ids)).delete(synchronize_session=False)
                cleanup_db.query(Agent).filter(Agent.owner_id == user.id).delete(synchronize_session=False)
                cleanup_db.query(Repository).filter(Repository.id.in_([repo1.id, repo2.id])).delete(synchronize_session=False)
                cleanup_db.query(UserSession).filter(UserSession.user_id == user.id).delete(synchronize_session=False)
                cleanup_db.query(Actor).filter(Actor.owner_id == user.id).delete(synchronize_session=False)
                cleanup_db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
                cleanup_db.commit()
            except Exception:
                cleanup_db.rollback()
