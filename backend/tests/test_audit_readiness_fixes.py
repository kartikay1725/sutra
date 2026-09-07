import hmac
import hashlib
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from app.api.dependencies import get_current_user
from app.api.agent_dependencies import get_current_agent_session
from app.core.config import settings
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.discussion import Discussion
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User


def _create_user_and_actor(db, username: str, email: str) -> tuple[User, Actor]:
    user = User(
        id=str(uuid4()),
        username=username,
        email=email,
        password_hash="test-hash",
    )
    db.add(user)
    db.flush()

    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=username,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.flush()
    return user, actor


def _create_repo(db, owner_user: User, name: str, visibility: str = "private") -> Repository:
    repo = Repository(
        id=str(uuid4()),
        owner_id=owner_user.id,
        name=name,
        slug=name.lower(),
        storage_key=str(uuid4()),
        default_branch="main",
        visibility=visibility,
    )
    db.add(repo)
    db.flush()
    return repo


def test_changes_idor_protection_direct_query(client, db):
    user_a, _ = _create_user_and_actor(db, "alice", "alice@example.com")
    user_b, _ = _create_user_and_actor(db, "bob", "bob@example.com")

    repo_a = _create_repo(db, user_a, "alice-secret-repo", visibility="private")
    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=user_a.id,
        intent="Secret feature for Alice",
        status="proposed",
    )
    db.add(change_a)
    db.commit()

    # User B tries to query Alice's private repository changes
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = client.get(f"/v1/changes?owner=alice&repo={repo_a.slug}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Repository not found"
    finally:
        app.dependency_overrides.clear()


def test_changes_idor_protection_global_list(client, db):
    user_a, _ = _create_user_and_actor(db, "alice2", "alice2@example.com")
    user_b, _ = _create_user_and_actor(db, "bob2", "bob2@example.com")

    repo_a = _create_repo(db, user_a, "alice-private-repo", visibility="private")
    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=user_a.id,
        intent="Alice private change",
        status="proposed",
    )
    db.add(change_a)

    repo_b = _create_repo(db, user_b, "bob-my-repo", visibility="private")
    change_b = Change(
        id=str(uuid4()),
        repository_id=repo_b.id,
        actor_id=user_b.id,
        intent="Bob own change",
        status="proposed",
    )
    db.add(change_b)
    db.commit()

    # Bob lists all changes without specifying owner/repo
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = client.get("/v1/changes")
        assert resp.status_code == 200
        change_ids = [c["id"] for c in resp.json()]
        assert change_b.id in change_ids
        assert change_a.id not in change_ids, "User A's private change leaked in global listing!"
    finally:
        app.dependency_overrides.clear()


def test_task_deletion_idor_protection(client, db):
    user_a, _ = _create_user_and_actor(db, "alice3", "alice3@example.com")
    user_b, _ = _create_user_and_actor(db, "bob3", "bob3@example.com")

    repo_a = _create_repo(db, user_a, "alice-tasks-repo", visibility="private")
    task_a = Task(
        id=str(uuid4()),
        repository_id=repo_a.id,
        created_by=user_a.id,
        title="Confidential architecture task",
        status="open",
        priority="high",
        task_type="feature",
        source="user",
    )
    db.add(task_a)
    db.commit()

    # Bob tries to delete Alice's task in private repo
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = client.delete(f"/v1/tasks/{task_a.id}")
        assert resp.status_code == 404, "Must return 404 to avoid leaking task existence"
    finally:
        app.dependency_overrides.clear()


def test_repository_activity_idor_protection(client, db):
    user_a, _ = _create_user_and_actor(db, "alice4", "alice4@example.com")
    user_b, _ = _create_user_and_actor(db, "bob4", "bob4@example.com")

    repo_a = _create_repo(db, user_a, "alice-activity-repo", visibility="private")
    db.commit()

    # Bob requests activity for Alice's private repository
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = client.get(f"/v1/repositories/alice4/{repo_a.slug}/activity")
        assert resp.status_code == 404, "Private repo activity must return 404 to avoid enumeration"
    finally:
        app.dependency_overrides.clear()


def test_agent_discussion_task_spoofing_prevented(client, db):
    from app.core.security import hash_password
    from app.models.agent_repository_access import AgentRepositoryAccess

    user_a, _ = _create_user_and_actor(db, "alice5", "alice5@example.com")
    repo_a = _create_repo(db, user_a, "alice-discuss-repo", visibility="public")

    # Agent 1
    raw_token = f"sutra_session_{uuid4().hex}_{uuid4().hex}"
    agent1 = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="agent-one",
        is_active=True,
        status="active",
        token_prefix="sutra_agent_1_",
        token_hash=hash_password("agent-secret"),
    )
    db.add(agent1)
    db.flush()

    actor1 = Actor(
        id=agent1.id,
        owner_id=user_a.id,
        type="agent",
        name=agent1.name,
        capabilities='["repository.read", "repository.write", "discussion.write"]',
    )
    db.add(actor1)

    session1 = AgentSession(
        id=str(uuid4()),
        agent_id=agent1.id,
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:32],
        status="active",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(session1)

    db.add(AgentRepositoryAccess(
        id=str(uuid4()),
        agent_id=agent1.id,
        repository_id=repo_a.id,
        enabled=True,
    ))

    # Agent 2 (different agent)
    agent2 = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="agent-two",
        is_active=True,
        status="active",
        token_prefix="sutra_agent_2_",
        token_hash=hash_password("agent2-secret"),
    )
    db.add(agent2)
    db.flush()

    # Task assigned to another agent (agent2)
    task_other = Task(
        id=str(uuid4()),
        repository_id=repo_a.id,
        created_by=user_a.id,
        assigned_agent_id=agent2.id,
        title="Other agent's task",
        status="in_progress",
        priority="medium",
        task_type="feature",
        source="user",
    )
    db.add(task_other)
    db.commit()

    headers = {"Authorization": f"Bearer {raw_token}"}

    # Agent 1 tries to create discussion claiming task_other
    resp = client.post(
        f"/v1/repositories/alice5/{repo_a.slug}/discussions",
        headers=headers,
        json={
            "title": "Agent discussion with forged task",
            "body": "Forging task linkage",
            "task_id": task_other.id,
        },
    )
    assert resp.status_code == 403
    assert "Agent is not assigned to this task" in resp.json()["detail"]


def test_webhook_pull_request_synchronize_invalidates_approval(client, db):
    user, _ = _create_user_and_actor(db, "gh-owner", "gh-owner@example.com")
    repo = _create_repo(db, user, "gh-repo", visibility="public")
    repo.provider_type = "github"
    repo.provider_owner = "gh-owner"
    repo.slug = "gh-repo"

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=user.id,
        intent="Initial change",
        resulting_commit="sha_old_1111",
        status="recorded",
        metadata_json=json.dumps({"approved_head_sha": "sha_old_1111", "github_pr_number": 42, "branch": "feature-x"}),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Feature PR",
        target_branch="main",
        source_commit="sha_old_1111",
        status="approved",
    )
    db.add(pr)
    db.commit()
    db.commit()

    # Webhook payload for pull_request synchronize (new commit pushed to PR)
    secret = "test-webhook-secret-key-32-chars!!"
    settings.github_webhook_secret = secret

    payload = {
        "action": "synchronize",
        "number": 42,
        "repository": {
            "name": "gh-repo",
            "owner": {"login": "gh-owner"},
        },
        "pull_request": {
            "number": 42,
            "head": {"ref": "feature-x", "sha": "sha_new_2222"},
            "base": {"ref": "main", "sha": "sha_base_0000"},
            "merged": False,
        },
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    resp = client.post(
        "/v1/webhooks/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert resp.json()["action"] == "synchronize"

    db.refresh(pr)
    db.refresh(change)
    assert pr.source_commit == "sha_new_2222"
    assert pr.status == "open", "Approval must be invalidated when PR HEAD changes!"
    change_meta = json.loads(change.metadata_json)
    assert change_meta.get("approved_head_sha") is None, "approved_head_sha must be reset!"
