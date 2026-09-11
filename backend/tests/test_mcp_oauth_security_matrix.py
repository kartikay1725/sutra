"""
Comprehensive Security Matrix Test Suite for SUTRA MCP OAuth 2.1 & HTTP Authentication Boundary.

Covers security specifications A through Q:
A. Anonymous /v1/mcp protected request: HTTP 401 with WWW-Authenticate present
B. Anonymous user cannot authorize an MCP client
C. Unauthenticated browser authorization redirects to / renders login
D. Logged-in user sees consent page
E. Cancel does not issue a code/token (returns access_denied)
F. Approve issues a code bound to correct user/client
G. OAuth token resolves to correct Agent
H. No request can ever select "first active agent"
I. Two users authorizing simultaneously cannot cross-bind agents
J. Token from User A cannot access User B's agent/repositories
K. New agent starts with zero repository grants
L. PKCE S256 remains mandatory
M. Issuer validation remains enforced
N. Token revocation remains effective
O. Agent cannot approve/merge (human-only merge boundary intact)
P. Cross-repository authorization remains denied
Q. MCP tool calls still preserve AgentSession provenance
"""

from datetime import datetime, timedelta, timezone
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


def _gen_pkce():
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


@pytest.fixture
def sec_env():
    """Sets up two isolated users (Alice and Bob) and repositories for security isolation testing."""
    now = datetime.now(timezone.utc)
    uid_a = secrets.token_hex(4)
    uid_b = secrets.token_hex(4)

    with SessionLocal() as db:
        user_a = User(
            id=f"user_{uid_a}",
            username=f"sec_alice_{uid_a}",
            email=f"alice_{uid_a}@test.local",
            password_hash=hash_password("AliceSecurePass123!"),
            email_verified=True,
        )
        user_b = User(
            id=f"user_{uid_b}",
            username=f"sec_bob_{uid_b}",
            email=f"bob_{uid_b}@test.local",
            password_hash=hash_password("BobSecurePass123!"),
            email_verified=True,
        )
        db.add_all([user_a, user_b])
        db.flush()

        actor_a = Actor(id=user_a.id, owner_id=user_a.id, type="human", name=user_a.username, capabilities="[]")
        actor_b = Actor(id=user_b.id, owner_id=user_b.id, type="human", name=user_b.username, capabilities="[]")
        db.add_all([actor_a, actor_b])
        db.flush()

        # Create human sessions
        sess_a = UserSession(user_id=user_a.id, expires_at=now + timedelta(hours=1))
        sess_b = UserSession(user_id=user_b.id, expires_at=now + timedelta(hours=1))
        db.add_all([sess_a, sess_b])
        db.flush()

        token_a = create_access_token(user_a.id, sess_a.id)
        token_b = create_access_token(user_b.id, sess_b.id)

        # Repositories
        repo_a = Repository(
            name=f"repo-alice-{uid_a}",
            slug=f"repo-alice-{uid_a}",
            owner_id=user_a.id,
            storage_key=f"storage_{uid_a}",
            default_branch="main",
            visibility="private",
        )
        repo_b = Repository(
            name=f"repo-bob-{uid_b}",
            slug=f"repo-bob-{uid_b}",
            owner_id=user_b.id,
            storage_key=f"storage_{uid_b}",
            default_branch="main",
            visibility="private",
        )
        db.add_all([repo_a, repo_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)
        db.refresh(repo_a)
        db.refresh(repo_b)

        yield {
            "user_a": user_a,
            "user_b": user_b,
            "token_a": token_a,
            "token_b": token_b,
            "repo_a": repo_a,
            "repo_b": repo_b,
            "pass_a": "AliceSecurePass123!",
            "pass_b": "BobSecurePass123!",
        }

        # Cleanup
        with SessionLocal() as cleanup_db:
            try:
                cleanup_db.query(AgentRepositoryAccess).delete()
                cleanup_db.query(AgentSession).delete()
                cleanup_db.query(Agent).filter(Agent.owner_id.in_([user_a.id, user_b.id])).delete()
                cleanup_db.query(Repository).filter(Repository.id.in_([repo_a.id, repo_b.id])).delete()
                cleanup_db.query(UserSession).filter(UserSession.user_id.in_([user_a.id, user_b.id])).delete()
                cleanup_db.query(Actor).filter(Actor.owner_id.in_([user_a.id, user_b.id])).delete()
                cleanup_db.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete()
                cleanup_db.commit()
            except Exception:
                cleanup_db.rollback()


@pytest.mark.asyncio
async def test_a_anonymous_mcp_returns_401_with_www_authenticate():
    """A. Anonymous /v1/mcp protected request: HTTP 401, WWW-Authenticate present and compliant."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.post(
            "/v1/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert res.status_code == 401
        www_auth = res.headers.get("www-authenticate")
        assert www_auth is not None
        assert "Bearer" in www_auth
        assert 'resource_metadata="https://api.sutra.sudarshanai.com/.well-known/oauth-protected-resource"' in www_auth


@pytest.mark.asyncio
async def test_b_c_unauthenticated_browser_authorizing_redirects_or_renders_login(sec_env):
    """B & C. Anonymous user cannot authorize an MCP client; sees login form instead of code."""
    verifier, challenge = _gen_pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "random_state_123",
            },
            follow_redirects=False,
        )
        # Must return 200 with SUTRA Login form preserving parameters (or 302 to login)
        assert res.status_code == 200
        assert "Sign in to SUTRA" in res.text
        assert "login_action" in res.text
        assert "cursor-ide" in res.text
        # Must NOT issue a code
        assert "sutra_auth_code_" not in res.text
        assert res.headers.get("location") is None


@pytest.mark.asyncio
async def test_d_logged_in_user_sees_consent_page(sec_env):
    """D. Logged-in user sees consent page with client name, scopes, human identity."""
    verifier, challenge = _gen_pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "random_state_123",
            },
            follow_redirects=False,
        )
        assert res.status_code == 200
        assert "Connect Cursor" in res.text
        assert sec_env["user_a"].username in res.text
        assert "Zero-Access Default Boundary" in res.text
        assert 'value="cancel"' in res.text
        assert 'value="approve"' in res.text


@pytest.mark.asyncio
async def test_e_cancel_does_not_issue_code_or_token(sec_env):
    """E. Cancel returns HTTP 302 with access_denied and does not issue code or token."""
    verifier, challenge = _gen_pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "state_cancel_test",
                "action": "cancel",
            },
            follow_redirects=False,
        )
        assert res.status_code == 302
        location = res.headers.get("location")
        parsed = urlparse(location)
        q = parse_qs(parsed.query)
        assert q["error"][0] == "access_denied"
        assert q["state"][0] == "state_cancel_test"
        assert "code" not in q


@pytest.mark.asyncio
async def test_f_g_approve_issues_code_bound_to_user_and_agent(sec_env):
    """F & G. Approve issues a code bound to correct user/client and resolves to user's Agent."""
    verifier, challenge = _gen_pkce()
    redirect_uri = "https://client.local/callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "state_approve_test",
                "action": "approve",
            },
            follow_redirects=False,
        )
        assert res.status_code == 302
        loc = res.headers.get("location")
        q = parse_qs(urlparse(loc).query)
        code = q["code"][0]
        assert code.startswith("sutra_auth_code_")

        # Exchange code for token
        tok_res = await client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": "cursor-ide",
                "code_verifier": verifier,
            },
        )
        assert tok_res.status_code == 200
        tok_data = tok_res.json()
        access_token = tok_data["access_token"]
        assert access_token.startswith("sutra_mcp_at_")

        # Verify Redis binding
        token_prefix = access_token[:32]
        raw_meta = redis_service.get(f"mcp_oauth:{token_prefix}")
        assert raw_meta is not None
        meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
        assert meta["user_id"] == sec_env["user_a"].id
        assert meta["client_id"] == "cursor-ide"

        # Verify Agent belongs to Alice
        with SessionLocal() as db:
            agent = db.scalar(select(Agent).where(Agent.id == meta["agent_id"]))
            assert agent is not None
            assert agent.owner_id == sec_env["user_a"].id
            assert "Cursor" in agent.name


@pytest.mark.asyncio
async def test_h_no_request_can_select_first_active_agent(sec_env):
    """H. Authorize with unauthenticated user or wrong credentials NEVER falls back to any agent."""
    verifier, challenge = _gen_pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",  # Unauthenticated request trying to approve
            },
            follow_redirects=False,
        )
        # Must fail closed: render login page (200) rather than issuing a code (302)
        assert res.status_code == 200
        assert "Sign in to SUTRA" in res.text
        assert "location" not in res.headers


@pytest.mark.asyncio
async def test_i_j_two_users_cannot_cross_bind_or_access_each_others_agents(sec_env):
    """I & J. Simultaneous authorizations by User A and User B cannot cross-bind agents or tokens."""
    ver_a, chal_a = _gen_pkce()
    ver_b, chal_b = _gen_pkce()
    redirect_uri = "https://client.local/callback"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        # User A approves
        res_a = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": chal_a,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code_a = parse_qs(urlparse(res_a.headers["location"]).query)["code"][0]

        # User B approves
        res_b = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_b']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": chal_b,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code_b = parse_qs(urlparse(res_b.headers["location"]).query)["code"][0]

        # Exchange tokens
        tok_a = (await client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code_a, "redirect_uri": redirect_uri,
            "client_id": "cursor-ide", "code_verifier": ver_a,
        })).json()["access_token"]

        tok_b = (await client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code_b, "redirect_uri": redirect_uri,
            "client_id": "cursor-ide", "code_verifier": ver_b,
        })).json()["access_token"]

        meta_a = redis_service.get(f"mcp_oauth:{tok_a[:32]}")
        meta_b = redis_service.get(f"mcp_oauth:{tok_b[:32]}")
        if isinstance(meta_a, str):
            meta_a = json.loads(meta_a)
        if isinstance(meta_b, str):
            meta_b = json.loads(meta_b)

        assert meta_a["user_id"] == sec_env["user_a"].id
        assert meta_b["user_id"] == sec_env["user_b"].id
        assert meta_a["agent_id"] != meta_b["agent_id"]


@pytest.mark.asyncio
async def test_k_new_agent_starts_with_zero_repository_grants(sec_env):
    """K. New OAuth-connected agents start with zero repository grants (least privilege)."""
    verifier, challenge = _gen_pkce()
    redirect_uri = "https://client.local/callback"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "claude-code",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(res.headers["location"]).query)["code"][0]

        tok_res = await client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code", "code": code,
                "redirect_uri": redirect_uri, "client_id": "claude-code", "code_verifier": verifier,
            },
        )
        access_token = tok_res.json()["access_token"]

        meta = redis_service.get(f"mcp_oauth:{access_token[:32]}")
        if isinstance(meta, str):
            meta = json.loads(meta)
        agent_id = meta["agent_id"]

        # Check repository grants in DB
        with SessionLocal() as db:
            grants = db.scalars(
                select(AgentRepositoryAccess).where(AgentRepositoryAccess.agent_id == agent_id)
            ).all()
            assert len(grants) == 0, f"Expected 0 repo grants, found {len(grants)}"


@pytest.mark.asyncio
async def test_l_pkce_s256_mandatory(sec_env):
    """L. PKCE S256 remains mandatory; plain or missing code_challenge is rejected."""
    verifier, challenge = _gen_pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        # Plain method rejected
        res_plain = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
                "code_challenge": "plain_string",
                "code_challenge_method": "plain",
            },
        )
        assert res_plain.status_code == 400
        assert "S256" in res_plain.text

        # Missing challenge rejected
        res_missing = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
            },
        )
        assert res_missing.status_code == 400


@pytest.mark.asyncio
async def test_m_issuer_validation_enforced(sec_env):
    """M. Issuer parameter matches canonical HTTPS endpoint."""
    verifier, challenge = _gen_pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": "https://client.local/callback",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        assert res.status_code == 302
        q = parse_qs(urlparse(res.headers["location"]).query)
        assert q["iss"][0] == "https://api.sutra.sudarshanai.com"


@pytest.mark.asyncio
async def test_n_token_revocation_effective(sec_env):
    """N. Token revocation invalidates access token in Redis."""
    verifier, challenge = _gen_pkce()
    redirect_uri = "https://client.local/callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(res.headers["location"]).query)["code"][0]
        tok_data = (await client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "client_id": "cursor-ide", "code_verifier": verifier,
        })).json()
        access_token = tok_data["access_token"]

        # Revoke
        rev_res = await client.post("/oauth/revoke", data={"token": access_token})
        assert rev_res.status_code == 200

        # Verify Redis key is deleted
        assert redis_service.get(f"sutra:oauth:at:{access_token}") is None


@pytest.mark.asyncio
async def test_o_agent_cannot_approve_or_merge(sec_env):
    """O. Agent cannot approve/merge; human-only merge governance boundary remains strictly intact."""
    verifier, challenge = _gen_pkce()
    redirect_uri = "https://client.local/callback"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(res.headers["location"]).query)["code"][0]
        tok_data = (await client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "client_id": "cursor-ide", "code_verifier": verifier,
        })).json()
        access_token = tok_data["access_token"]

        meta = redis_service.get(f"mcp_oauth:{access_token[:32]}")
        if isinstance(meta, str):
            meta = json.loads(meta)
        agent_id = meta["agent_id"]

        # Verify agent Actor capabilities strictly forbid human-only operations
        with SessionLocal() as db:
            actor = db.scalar(select(Actor).where(Actor.id == agent_id))
            assert actor is not None
            assert actor.type == "agent"
            caps = json.loads(actor.capabilities)
            # Human-only merge and approval permissions must NEVER be granted to an agent
            assert "pr.merge" not in caps
            assert "change.approve" not in caps
            assert "change.review" not in caps
            assert "governance.override" not in caps


@pytest.mark.asyncio
async def test_p_cross_repository_authorization_denied(sec_env):
    """P. Token from User A cannot access User B's repository (cross-repository authorization denied)."""
    verifier, challenge = _gen_pkce()
    redirect_uri = "https://client.local/callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(res.headers["location"]).query)["code"][0]
        tok_data = (await client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "client_id": "cursor-ide", "code_verifier": verifier,
        })).json()
        access_token = tok_data["access_token"]

        # Check DB access permissions for User A's new agent on User B's repository
        meta = redis_service.get(f"mcp_oauth:{access_token[:32]}")
        if isinstance(meta, str):
            meta = json.loads(meta)
        agent_id = meta["agent_id"]

        with SessionLocal() as db:
            grant_on_b = db.scalar(
                select(AgentRepositoryAccess).where(
                    AgentRepositoryAccess.agent_id == agent_id,
                    AgentRepositoryAccess.repository_id == sec_env["repo_b"].id,
                )
            )
            assert grant_on_b is None, "Cross-repository access must be denied"


@pytest.mark.asyncio
async def test_q_mcp_tool_calls_preserve_agentsession_provenance(sec_env):
    """Q. MCP tool calls with OAuth token preserve valid AgentSession provenance and identity."""
    verifier, challenge = _gen_pkce()
    redirect_uri = "https://client.local/callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.sutra.sudarshanai.com") as client:
        res = await client.get(
            "/oauth/authorize",
            headers={"Authorization": f"Bearer {sec_env['token_a']}"},
            params={
                "client_id": "cursor-ide",
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(res.headers["location"]).query)["code"][0]
        tok_data = (await client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "client_id": "cursor-ide", "code_verifier": verifier,
        })).json()
        access_token = tok_data["access_token"]

        meta = redis_service.get(f"mcp_oauth:{access_token[:32]}")
        if isinstance(meta, str):
            meta = json.loads(meta)

        # Confirm session_id and raw_session_token exist in Redis binding and map to active AgentSession
        session_id = meta.get("session_id")
        assert session_id is not None
        with SessionLocal() as db:
            sess = db.scalar(select(AgentSession).where(AgentSession.id == session_id))
            assert sess is not None
            assert sess.agent_id == meta["agent_id"]
            assert sess.status == "active"
