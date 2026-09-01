import os
import shutil
import tempfile
import subprocess
import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
import httpx

from app.core.config import settings
from app.models.user import User
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.repository import Repository
from app.models.change import Change
from app.core.security import hash_password
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.credentials import GitHubCredentialProvider
from app.providers.github.repository import GitHubRepositoryProvider
from app.providers.github.events import GitHubWebhookAdapter
from app.services.git_push_event_service import GitPushEventService


@pytest.fixture(scope="module")
def live_auth_service():
    if not settings.github_app_id or not settings.github_private_key_pem:
        pytest.skip("GitHub App credentials not configured in environment")
    return GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )


def test_step2_and_3_live_app_jwt_and_installation_discovery(live_auth_service):
    jwt_token = live_auth_service.generate_app_jwt()
    assert isinstance(jwt_token, str)
    assert len(jwt_token) > 50

    owner = settings.github_test_repo_owner
    repo = settings.github_test_repo_name
    inst_id = live_auth_service.get_installation_id(owner, repo)
    assert inst_id > 0
    print(f"\n[LIVE] Installation discovery: PASS (Installation ID: {inst_id})")


def test_step4_and_5_live_installation_token_and_negative_scope(live_auth_service):
    owner = settings.github_test_repo_owner
    repo = settings.github_test_repo_name
    inst_id = live_auth_service.get_installation_id(owner, repo)

    # Step 4: Token issuance scoped ONLY to sutra-github-e2e-dev
    token_data = live_auth_service.create_installation_token(
        installation_id=inst_id,
        repositories=[repo],
        permissions={"metadata": "read", "contents": "read"},
    )

    token = token_data["token"]
    assert token.startswith("ghs_")
    assert repo in token_data["repositories"]
    assert token_data["permissions"]["contents"] == "read"
    print(f"\n[LIVE] Token issuance: PASS (Repository scope: {owner}/{repo}, Permissions: {token_data['permissions']})")

    # Step 5: Negative Scope Test: Attempt access to unauthorized repository
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # Query another repository
    res = httpx.get("https://api.github.com/repos/kartikay1725/unauthorized-other-repo-xyz/contents", headers=headers)
    assert res.status_code in {401, 403, 404}
    print(f"\n[LIVE] Negative Cross-Repository Scope Test: PASS (HTTP {res.status_code} rejection)")

    live_auth_service.revoke_installation_token(token)


def test_step6_live_github_repository_metadata(live_auth_service):
    owner = settings.github_test_repo_owner
    repo = settings.github_test_repo_name

    provider = GitHubRepositoryProvider(live_auth_service)
    meta = provider.get_repository_metadata(owner, repo)

    assert meta.provider_type == "github"
    assert meta.owner == owner
    assert meta.name == repo
    assert meta.default_branch == "main"
    assert meta.capabilities["check_runs"] is True
    print(f"\n[LIVE] Repository metadata: PASS (Owner: {meta.owner}, Repo: {meta.name}, Default Branch: {meta.default_branch})")


def test_step7_and_8_live_git_clone_and_readonly_push_rejection(live_auth_service):
    owner = settings.github_test_repo_owner
    repo = settings.github_test_repo_name
    inst_id = live_auth_service.get_installation_id(owner, repo)

    token_data = live_auth_service.create_installation_token(
        installation_id=inst_id,
        repositories=[repo],
        permissions={"metadata": "read", "contents": "read"},
    )
    ro_token = token_data["token"]

    tmp_dir = tempfile.mkdtemp(prefix="sutra-test-clone-ro-")
    clone_url = f"https://x-access-token:{ro_token}@github.com/{owner}/{repo}.git"

    try:
        # Step 7: Real Read-Only Clone
        res = subprocess.run(
            ["git", "clone", clone_url, tmp_dir],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Git clone failed: {res.stderr}"
        assert os.path.exists(os.path.join(tmp_dir, "README.md"))
        print("\n[LIVE] Real Git Clone (Read-Only Token): PASS")

        # Step 8: Attempt push with Read-Only token — MUST FAIL (HTTP 403)
        sample_file = os.path.join(tmp_dir, "src", "example.txt")
        if os.path.exists(sample_file):
            with open(sample_file, "a") as f:
                f.write("\nUnauthorized modification test.")
            
            subprocess.run(["git", "-C", tmp_dir, "config", "user.name", "Test Agent"], check=True)
            subprocess.run(["git", "-C", tmp_dir, "config", "user.email", "agent@sutra.dev"], check=True)
            subprocess.run(["git", "-C", tmp_dir, "commit", "-am", "Unauthorized test commit"], check=True)
            
            push_res = subprocess.run(
                ["git", "-C", tmp_dir, "push", "origin", "main"],
                capture_output=True,
                text=True,
                check=False,
            )
            assert push_res.returncode != 0
            assert ("403" in push_res.stderr or "Permission" in push_res.stderr or "denied" in push_res.stderr)
            print("\n[LIVE] Read-Only Token Push Rejection: PASS (Rejected by GitHub)")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        live_auth_service.revoke_installation_token(ro_token)


def test_step9_10_18_19_live_write_token_and_feature_branch_push(db, client, live_auth_service):
    owner_username = settings.github_test_repo_owner
    repo_slug = settings.github_test_repo_name

    # 1. Setup SUTRA User, Repo, Agent, Session, and Capability
    user = User(username=owner_username, email=f"{owner_username}@example.com", password_hash=hash_password("pw"))
    db.add(user)
    db.commit()

    user_actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(user_actor)

    repo = Repository(
        owner_id=user.id,
        name=repo_slug,
        slug=repo_slug.lower(),
        storage_key="live-gh-storage-key",
        default_branch="main",
        visibility="public",
    )
    setattr(repo, "provider_type", "github")
    db.add(repo)
    db.commit()

    agent = Agent(
        owner_id=user.id,
        name="sutra-live-test-agent",
        token_hash=hash_password("sutra_agent_live_perm"),
        token_prefix="sutra_agent_perm",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create", "change.commit"]',
    )
    db.add(agent_actor)

    repo_access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions='["repository.read", "repository.write", "change.create", "change.commit"]',
        enabled=True,
    )
    db.add(repo_access)
    db.commit()

    now = datetime.now(timezone.utc)
    raw_session = "sutra_session_live_test_1234567890abcdef"
    session = AgentSession(
        agent_id=agent.id,
        token_hash=hash_password(raw_session),
        token_prefix=raw_session[:32],
        status="active",
        expires_at=now + timedelta(minutes=15),
    )
    db.add(session)
    db.commit()

    # Step 18: Permutation A: No session -> DENIED
    res_no_session = client.post(
        f"/v1/repositories/{owner_username}/{repo.slug}/token",
        headers={"Authorization": "Bearer invalid_session_xyz"},
        json={"capabilities": ["repository.write"]},
    )
    assert res_no_session.status_code in {401, 403}

    # Step 18: Permutation B: Session with write capability -> ALLOWED
    res_token = client.post(
        f"/v1/repositories/{owner_username}/{repo.slug}/token",
        headers={"Authorization": f"Bearer {raw_session}"},
        json={
            "capabilities": ["repository.read", "repository.write"],
            "max_ttl_seconds": 600,
        },
    )
    assert res_token.status_code == 200
    token_resp = res_token.json()
    write_token = token_resp["token"]
    assert token_resp["permissions"]["contents"] == "write"
    assert token_resp["effective_ttl_seconds"] == 600
    print("\n[LIVE] SUTRA Token Broker Write Credential Issuance: PASS")

    # Step 10: Real Git Clone & Push to Feature Branch
    tmp_dir = tempfile.mkdtemp(prefix="sutra-test-clone-wr-")
    clone_url = f"https://x-access-token:{write_token}@github.com/{owner_username}/{repo_slug}.git"
    unique_suffix = int(datetime.now().timestamp())
    feature_branch = f"sutra/agent-live-{unique_suffix}"

    try:
        clone_res = subprocess.run(["git", "clone", clone_url, tmp_dir], capture_output=True, text=True, check=False)
        assert clone_res.returncode == 0

        subprocess.run(["git", "-C", tmp_dir, "config", "user.name", "SUTRA Live Agent"], check=True)
        subprocess.run(["git", "-C", tmp_dir, "config", "user.email", "agent@sutra.dev"], check=True)
        subprocess.run(["git", "-C", tmp_dir, "checkout", "-b", feature_branch], check=True)

        example_file = os.path.join(tmp_dir, "src", "example.txt")
        with open(example_file, "a") as f:
            f.write(f"\nLive agent change timestamp: {datetime.now(timezone.utc).isoformat()}")

        subprocess.run(["git", "-C", tmp_dir, "commit", "-am", f"Live agent feature commit: {feature_branch}"], check=True)
        
        # Push feature branch
        push_res = subprocess.run(
            ["git", "-C", tmp_dir, "push", "-u", "origin", feature_branch],
            capture_output=True,
            text=True,
            check=False,
        )
        assert push_res.returncode == 0, f"Feature branch push failed: {push_res.stderr}"
        print(f"\n[LIVE] Real Feature Branch Push: PASS (Branch: {feature_branch})")

        # Verify branch exists via GitHub API
        gh_provider = GitHubRepositoryProvider(live_auth_service)
        branch_obj = gh_provider.get_branch(owner_username, repo_slug, feature_branch)
        assert branch_obj is not None
        assert branch_obj.name == feature_branch
        print(f"\n[LIVE] GitHub Remote Branch Verification: PASS (HEAD SHA: {branch_obj.commit_sha})")

        # Step 19: Verify downstream token CANNOT authenticate to SUTRA
        unauth_sutra_res = client.post(
            f"/v1/repositories/{owner_username}/{repo.slug}/token",
            headers={"Authorization": f"Bearer {write_token}"},
            json={"capabilities": ["repository.read"]},
        )
        assert unauth_sutra_res.status_code in {401, 403}
        print("\n[LIVE] Downstream GitHub Token Cannot Authenticate to SUTRA: PASS")

    finally:
        # Cleanup remote test branch & local tmp dir
        try:
            subprocess.run(["git", "-C", tmp_dir, "push", "origin", "--delete", feature_branch], capture_output=True, check=False)
        except Exception:
            pass
        shutil.rmtree(tmp_dir, ignore_errors=True)
        live_auth_service.revoke_installation_token(write_token)


def test_step14_to_17_live_webhook_hmac_and_replay_idempotency(db, client):
    owner = settings.github_test_repo_owner
    repo_name = settings.github_test_repo_name

    # Setup user, actor, and repository in DB
    user = User(username=owner, email=f"{owner}@example.com", password_hash=hash_password("pw"))
    db.add(user)
    db.commit()

    user_actor = Actor(id=user.id, owner_id=user.id, type="human", name=user.username)
    db.add(user_actor)

    agent = Agent(owner_id=user.id, name="agent-wh", token_hash="hash", token_prefix="pref", status="active", is_active=True)
    db.add(agent)
    db.flush()

    agent_actor = Actor(id=agent.id, owner_id=user.id, type="agent", name=agent.name)
    db.add(agent_actor)

    repo = Repository(
        owner_id=user.id,
        name=repo_name,
        slug=repo_name.lower(),
        storage_key="live-wh-storage-key",
        default_branch="main",
        visibility="public",
    )
    setattr(repo, "provider_type", "github")
    db.add(repo)
    db.flush()

    repo_access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions='["repository.read", "repository.write"]',
        enabled=True,
    )
    db.add(repo_access)
    db.commit()

    head_sha = "f0e1d2c3b4a5968778695a4b3c2d1e0f12345678"
    webhook_payload = {
        "repository": {
            "name": repo_name,
            "owner": {"login": owner},
        },
        "ref": "refs/heads/sutra/agent-webhook-test",
        "before": "0000000000000000000000000000000000000000",
        "after": head_sha,
        "created": True,
        "deleted": False,
        "forced": False,
        "pusher": {"name": owner},
        "commits": [{"id": head_sha}],
    }
    payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    secret = settings.github_webhook_secret or settings.jwt_secret
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    invalid_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    # Step 16: Invalid signature rejection
    res_invalid = client.post(
        "/v1/webhooks/github",
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": invalid_sig},
        content=payload_bytes,
    )
    assert res_invalid.status_code == 401
    print("\n[LIVE] Invalid Webhook Signature Rejection: PASS (Rejected with HTTP 401)")

    # Step 14/15: Valid HMAC webhook processing
    res_valid = client.post(
        "/v1/webhooks/github",
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": valid_sig},
        content=payload_bytes,
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "processed"
    print("\n[LIVE] Valid Webhook HMAC Signature & Persistence: PASS")

    # Step 17: Duplicate webhook replay
    res_replay = client.post(
        "/v1/webhooks/github",
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": valid_sig},
        content=payload_bytes,
    )
    assert res_replay.status_code == 200
    print("\n[LIVE] Duplicate Webhook Replay Tolerated: PASS")
