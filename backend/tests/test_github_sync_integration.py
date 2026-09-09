import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.issue import Issue, IssueComment
from app.models.knowledge_node import KnowledgeNode
from app.models.knowledge_edge import KnowledgeEdge
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services import knowledge_graph_service
from app.services.github_installation_service import GitHubInstallationService


def _sign_payload(secret: str, payload_dict: dict) -> tuple[bytes, str]:
    body_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return body_bytes, sig


def _create_test_environment(db, username="gh-sync-user", repo_name="sync-repo", external_id="12345678"):
    user = User(
        id=str(uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
        email_verified=True,
    )
    db.add(user)
    db.flush()

    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=username,
        capabilities="[]",
    )
    db.add(actor)
    db.flush()

    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name=repo_name,
        slug=repo_name.lower(),
        storage_key=f"repos/{username}/{repo_name}",
        provider_type="github",
        external_id=external_id,
        provider_owner=username,
        visibility="public",
        default_branch="main",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return user, repo


def test_github_webhook_issue_opened(client, db):
    """Test A: GitHub webhook issue opened ingests correctly as human-originated."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-a", "repo-a", external_id="888001")

    payload = {
        "action": "opened",
        "repository": {
            "id": 888001,
            "name": "repo-a",
            "owner": {"login": "owner-a"},
        },
        "issue": {
            "id": 10101,
            "number": 1,
            "title": "Bug found on GitHub",
            "body": "Detailed description of the bug.",
            "state": "open",
            "html_url": "https://github.com/owner-a/repo-a/issues/1",
            "user": {"login": "gh-contributor"},
            "created_at": "2026-09-09T10:00:00Z",
            "updated_at": "2026-09-09T10:00:00Z",
            "closed_at": None,
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    issue = db.scalar(
        select(Issue).where(
            Issue.repository_id == repo.id,
            Issue.github_issue_number == 1,
        )
    )
    assert issue is not None
    assert issue.title == "Bug found on GitHub"
    assert issue.body == "Detailed description of the bug."
    assert issue.status == "open"
    assert issue.source_type == "human"
    assert issue.agent_id is None
    assert issue.agent_session_id is None
    assert issue.task_id is None
    assert issue.github_author_login == "gh-contributor"
    assert issue.github_html_url == "https://github.com/owner-a/repo-a/issues/1"


def test_github_webhook_issue_closed(client, db):
    """Test B: Issue closed via webhook sets status to closed and sets closed_at."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-b", "repo-b", external_id="888002")

    # Seed open issue
    issue = Issue(
        id=str(uuid4()),
        repository_id=repo.id,
        github_issue_id="10102",
        github_issue_number=2,
        title="Issue to be closed",
        body="Body",
        status="open",
        source_type="human",
    )
    db.add(issue)
    db.commit()

    payload = {
        "action": "closed",
        "repository": {
            "id": 888002,
            "name": "repo-b",
            "owner": {"login": "owner-b"},
        },
        "issue": {
            "id": 10102,
            "number": 2,
            "title": "Issue to be closed",
            "body": "Body",
            "state": "closed",
            "html_url": "https://github.com/owner-b/repo-b/issues/2",
            "user": {"login": "gh-contributor"},
            "created_at": "2026-09-09T10:00:00Z",
            "updated_at": "2026-09-09T11:00:00Z",
            "closed_at": "2026-09-09T11:00:00Z",
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    db.refresh(issue)
    assert issue.status == "closed"
    assert issue.closed_at is not None


def test_github_webhook_issue_reopened(client, db):
    """Test C: Issue reopened via webhook transitions to open with closed_at cleared."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-c", "repo-c", external_id="888003")

    issue = Issue(
        id=str(uuid4()),
        repository_id=repo.id,
        github_issue_id="10103",
        github_issue_number=3,
        title="Issue to reopen",
        body="Body",
        status="closed",
        source_type="human",
        closed_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.commit()

    payload = {
        "action": "reopened",
        "repository": {
            "id": 888003,
            "name": "repo-c",
            "owner": {"login": "owner-c"},
        },
        "issue": {
            "id": 10103,
            "number": 3,
            "title": "Issue to reopen",
            "body": "Body",
            "state": "open",
            "html_url": "https://github.com/owner-c/repo-c/issues/3",
            "user": {"login": "gh-contributor"},
            "created_at": "2026-09-09T10:00:00Z",
            "updated_at": "2026-09-09T12:00:00Z",
            "closed_at": None,
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    db.refresh(issue)
    assert issue.status == "open"
    assert issue.closed_at is None


def test_github_webhook_issue_idempotent(client, db):
    """Test D: Re-delivering issue webhook does not duplicate issues."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-d", "repo-d", external_id="888004")

    payload = {
        "action": "opened",
        "repository": {
            "id": 888004,
            "name": "repo-d",
            "owner": {"login": "owner-d"},
        },
        "issue": {
            "id": 10104,
            "number": 4,
            "title": "Idempotent Issue",
            "body": "Original body",
            "state": "open",
            "html_url": "https://github.com/owner-d/repo-d/issues/4",
            "user": {"login": "gh-user"},
            "created_at": "2026-09-09T10:00:00Z",
            "updated_at": "2026-09-09T10:00:00Z",
        },
    }
    body, sig = _sign_payload(secret, payload)

    # Deliver once
    r1 = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": "delivery-1",
            "Content-Type": "application/json",
        },
    )
    assert r1.status_code == 200

    # Deliver again with another delivery ID
    r2 = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": "delivery-2",
            "Content-Type": "application/json",
        },
    )
    assert r2.status_code == 200

    issues = db.scalars(
        select(Issue).where(
            Issue.repository_id == repo.id,
            Issue.github_issue_number == 4,
        )
    ).all()
    assert len(issues) == 1


def test_github_webhook_pr_opened_external(client, db):
    """Test E: GitHub-created PR creates external Change without agent provenance."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-e", "repo-e", external_id="888005")

    payload = {
        "action": "opened",
        "number": 11,
        "repository": {
            "id": 888005,
            "name": "repo-e",
            "owner": {"login": "owner-e"},
        },
        "pull_request": {
            "number": 11,
            "title": "External Contributor PR",
            "body": "Fixing a bug from outside SUTRA",
            "html_url": "https://github.com/owner-e/repo-e/pull/11",
            "head": {"ref": "patch-1", "sha": "head_sha_1111"},
            "base": {"ref": "main", "sha": "base_sha_0000"},
            "user": {"login": "external-contributor"},
            "merged": False,
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200

    pr = db.scalar(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.title == "External Contributor PR",
        )
    )
    assert pr is not None
    assert pr.source_commit == "head_sha_1111"
    assert pr.target_branch == "main"
    assert pr.status == "open"

    # Verify Change backing the PR
    change = db.scalar(select(Change).where(Change.id == pr.source_change_id))
    assert change is not None
    meta = json.loads(change.metadata_json)
    assert meta["source"] == "github"
    assert meta["source_type"] == "github"
    assert meta["github_pr_number"] == 11
    # Check no fabricated agent provenance
    assert "agent_id" not in meta or meta.get("agent_id") is None
    assert "task_id" not in meta or meta.get("task_id") is None


def test_github_webhook_pr_idempotent(client, db):
    """Test F: Repeated PR webhook delivery does not create duplicate PRs or Changes."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-f", "repo-f", external_id="888006")

    payload = {
        "action": "opened",
        "number": 12,
        "repository": {
            "id": 888006,
            "name": "repo-f",
            "owner": {"login": "owner-f"},
        },
        "pull_request": {
            "number": 12,
            "title": "Idempotent PR",
            "body": "PR description",
            "html_url": "https://github.com/owner-f/repo-f/pull/12",
            "head": {"ref": "patch-2", "sha": "head_sha_2222"},
            "base": {"ref": "main", "sha": "base_sha_0000"},
            "user": {"login": "dev"},
            "merged": False,
        },
    }
    body, sig = _sign_payload(secret, payload)

    r1 = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "X-GitHub-Delivery": "d1", "Content-Type": "application/json"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "X-GitHub-Delivery": "d2", "Content-Type": "application/json"},
    )
    assert r2.status_code == 200

    prs = db.scalars(select(PullRequest).where(PullRequest.repository_id == repo.id)).all()
    assert len(prs) == 1


def test_github_webhook_pr_synchronize_invalidates_approval(client, db):
    """Test G: PR synchronize updates head sha and invalidates prior approval."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-g", "repo-g", external_id="888007")

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=user.id,
        intent="Change for PR 13",
        resulting_commit="sha_old_13",
        status="recorded",
        metadata_json=json.dumps({"approved_head_sha": "sha_old_13", "github_pr_number": 13, "branch": "feat-13"}),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="PR 13",
        target_branch="main",
        source_commit="sha_old_13",
        status="approved",
    )
    db.add(pr)
    db.commit()

    payload = {
        "action": "synchronize",
        "number": 13,
        "repository": {
            "id": 888007,
            "name": "repo-g",
            "owner": {"login": "owner-g"},
        },
        "pull_request": {
            "number": 13,
            "head": {"ref": "feat-13", "sha": "sha_new_13"},
            "base": {"ref": "main", "sha": "base_sha_00"},
            "merged": False,
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    db.refresh(pr)
    db.refresh(change)
    assert pr.source_commit == "sha_new_13"
    assert pr.status == "open"
    meta = json.loads(change.metadata_json)
    assert meta.get("approved_head_sha") is None


def test_github_webhook_repository_resolution_by_external_identity(client, db):
    """Test H: Repository resolves by external_id even when owner or name is ambiguous."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret

    # Two repos with same name but different external_id and owners
    user1, repo1 = _create_test_environment(db, "owner-h1", "common-name", external_id="999001")
    user2, repo2 = _create_test_environment(db, "owner-h2", "common-name", external_id="999002")

    payload = {
        "action": "opened",
        "repository": {
            "id": 999002,
            "name": "common-name",
            "owner": {"login": "owner-h2"},
        },
        "issue": {
            "id": 88001,
            "number": 50,
            "title": "Specific to repo2",
            "body": "Body",
            "state": "open",
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    # Ensure issue went to repo2 ONLY
    issue2 = db.scalar(select(Issue).where(Issue.repository_id == repo2.id, Issue.github_issue_number == 50))
    assert issue2 is not None
    issue1 = db.scalar(select(Issue).where(Issue.repository_id == repo1.id, Issue.github_issue_number == 50))
    assert issue1 is None


def test_github_webhook_rejects_invalid_signature(client, db):
    """Test I: Webhook with forged signature is rejected with HTTP 401."""
    payload = {"zen": "Keep it logically awesome."}
    body = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": "sha256=forgedbadhash1234567890abcdef",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


def test_agent_created_issue_preserves_agent_provenance_after_webhook(client, db):
    """Test O: Agent-created Issue keeps agent provenance after receiving a GitHub webhook update."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-o", "repo-o", external_id="888015")

    # Create agent, task, session
    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="EngineerBot",
        model="gpt-4o",
        status="active",
        token_hash="dummy_token_hash_value_12345",
        token_prefix="sutra_agent_t1",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        title="Agent Task",
        status="in_progress",
    )
    db.add(task)
    db.flush()

    session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="dummy_session_hash_value",
        token_prefix="sutra_session_t1",
        status="active",
        expires_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()

    # Agent created issue
    issue = Issue(
        id=str(uuid4()),
        repository_id=repo.id,
        github_issue_id="77701",
        github_issue_number=77,
        title="Issue by Agent",
        body="Initial agent body",
        status="open",
        source_type="agent",
        agent_id=agent.id,
        agent_session_id=session.id,
        task_id=task.id,
    )
    db.add(issue)
    db.commit()

    # Incoming edited webhook from GitHub
    payload = {
        "action": "edited",
        "repository": {
            "id": 888015,
            "name": "repo-o",
            "owner": {"login": "owner-o"},
        },
        "issue": {
            "id": 77701,
            "number": 77,
            "title": "Issue by Agent (Updated on GitHub)",
            "body": "Updated body from GitHub UI",
            "state": "open",
            "html_url": "https://github.com/owner-o/repo-o/issues/77",
            "user": {"login": "human-reviewer"},
            "updated_at": "2026-09-09T14:00:00Z",
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    db.refresh(issue)
    # Content updated
    assert issue.title == "Issue by Agent (Updated on GitHub)"
    assert issue.body == "Updated body from GitHub UI"
    # Provenance PRESERVED: must NOT be overwritten with null
    assert issue.source_type == "agent"
    assert issue.agent_id == agent.id
    assert issue.agent_session_id == session.id
    assert issue.task_id == task.id


def test_agent_created_pr_preserves_agent_provenance_after_webhook(client, db):
    """Test P: Agent-created PR preserves agent/task provenance after receiving webhook."""
    secret = "test-secret-32-chars-for-hmac!!"
    settings.github_webhook_secret = secret
    user, repo = _create_test_environment(db, "owner-p", "repo-p", external_id="888016")

    agent_id = str(uuid4())
    task_id = str(uuid4())
    agent_actor = Actor(
        id=agent_id,
        owner_id=user.id,
        type="agent",
        name="AutoAgent",
        capabilities="[]",
    )
    db.add(agent_actor)
    db.flush()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Autonomous implementation",
        resulting_commit="sha_agent_01",
        status="recorded",
        metadata_json=json.dumps({
            "source": "sutra",
            "source_type": "agent",
            "agent_id": agent_id,
            "task_id": task_id,
            "github_pr_number": 88,
            "branch": "sutra/agent-task-88",
        }),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=agent_actor.id,
        source_change_id=change.id,
        title="Agent Autonomous PR",
        target_branch="main",
        source_commit="sha_agent_01",
        status="open",
    )
    db.add(pr)
    db.commit()

    payload = {
        "action": "edited",
        "number": 88,
        "repository": {
            "id": 888016,
            "name": "repo-p",
            "owner": {"login": "owner-p"},
        },
        "pull_request": {
            "number": 88,
            "title": "Agent Autonomous PR (Title Edited)",
            "body": "PR description updated",
            "head": {"ref": "sutra/agent-task-88", "sha": "sha_agent_01"},
            "base": {"ref": "main", "sha": "base_00"},
            "merged": False,
        },
    }
    body, sig = _sign_payload(secret, payload)

    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    db.refresh(pr)
    db.refresh(change)
    assert pr.title == "Agent Autonomous PR (Title Edited)"
    assert pr.author_id == agent_actor.id
    meta = json.loads(change.metadata_json)
    assert meta.get("agent_id") == agent_id
    assert meta.get("task_id") == task_id


def test_knowledge_graph_indexes_github_issue(db):
    """Test K: KG indexes GitHub issue into a node."""
    user, repo = _create_test_environment(db, "owner-k", "repo-k", external_id="888011")

    issue = Issue(
        id=str(uuid4()),
        repository_id=repo.id,
        github_issue_id="12345",
        github_issue_number=10,
        title="GitHub Issue for KG",
        body="Testing KG indexing",
        status="open",
        source_type="human",
    )
    db.add(issue)
    db.commit()

    knowledge_graph_service.index_engineering_lifecycle(db, repo)
    db.commit()

    node = db.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.repository_id == repo.id,
            KnowledgeNode.entity_type == "issue",
            KnowledgeNode.name == "Issue #10: GitHub Issue for KG",
        )
    )
    assert node is not None


def test_knowledge_graph_indexes_github_pr(db):
    """Test L: KG indexes GitHub PR into a node and reviewed_in edge to change."""
    user, repo = _create_test_environment(db, "owner-l", "repo-l", external_id="888012")

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=user.id,
        intent="External PR change",
        resulting_commit="sha_pr_node",
        status="recorded",
        metadata_json=json.dumps({"github_pr_number": 25}),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="External PR for KG",
        target_branch="main",
        status="open",
    )
    db.add(pr)
    db.commit()

    knowledge_graph_service.index_engineering_lifecycle(db, repo)
    db.commit()

    pr_node = db.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.repository_id == repo.id,
            KnowledgeNode.entity_type == "pull_request",
        )
    )
    assert pr_node is not None

    change_node = db.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.repository_id == repo.id,
            KnowledgeNode.entity_type == "change",
        )
    )
    assert change_node is not None

    edge = db.scalar(
        select(KnowledgeEdge).where(
            KnowledgeEdge.source_node_id == change_node.id,
            KnowledgeEdge.target_node_id == pr_node.id,
            KnowledgeEdge.relationship_type == "reviewed_in",
        )
    )
    assert edge is not None


def test_knowledge_graph_returns_edges(client, db):
    """Test M: GET /v1/repositories/{owner}/{repo}/graph returns both nodes and edges."""
    user, repo = _create_test_environment(db, "owner-m", "repo-m", external_id="888013")

    node1 = KnowledgeNode(
        id=str(uuid4()),
        repository_id=repo.id,
        entity_type="module",
        name="core",
        metadata_json="{}",
    )
    node2 = KnowledgeNode(
        id=str(uuid4()),
        repository_id=repo.id,
        entity_type="file",
        name="core/app.py",
        metadata_json="{}",
    )
    db.add(node1)
    db.add(node2)
    db.flush()

    edge = KnowledgeEdge(
        id=str(uuid4()),
        source_node_id=node1.id,
        target_node_id=node2.id,
        relationship_type="contains",
    )
    db.add(edge)
    db.commit()

    # User token for API auth
    from app.core.security import create_access_token
    token = create_access_token(user.id)

    resp = client.get(
        f"/v1/repositories/owner-m/repo-m/graph",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1
    edge_resp = data["edges"][0]
    assert edge_resp["relationship_type"] == "contains"


def test_private_repository_graph_isolation(client, db):
    """Test N: Non-authorized user cannot access private repository graph."""
    user, repo = _create_test_environment(db, "owner-n", "private-repo", external_id="888014")
    repo.visibility = "private"
    db.commit()

    # Different user
    other_user = User(
        id=str(uuid4()),
        username="unauthorized-user",
        email="unauthorized@example.com",
        password_hash="test-hash",
        email_verified=True,
    )
    db.add(other_user)
    db.commit()

    from app.core.security import create_access_token
    token = create_access_token(other_user.id)

    resp = client.get(
        f"/v1/repositories/owner-n/private-repo/graph",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Private repository should return 404 to avoid leaking existence
    assert resp.status_code == 404


def test_repository_sync_backfills_issues_and_prs(db, monkeypatch):
    """Test J: sync_repository_engineering_objects idempotently backfills issues and PRs without fake provenance."""
    user, repo = _create_test_environment(db, "owner-j", "repo-j", external_id="888010")

    from app.providers.base import ProviderIssue, ProviderPullRequest
    from app.providers.github.repository import GitHubRepositoryProvider

    mock_issues = [
        ProviderIssue(
            id="gh_issue_100",
            number=100,
            title="Backfill Issue 100",
            body="Backfill body",
            state="open",
            author_login="gh-backfill-user",
            author_name="Backfill User",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            closed_at=None,
            html_url="https://github.com/owner-j/repo-j/issues/100",
        )
    ]

    mock_prs = [
        ProviderPullRequest(
            number=200,
            title="Backfill PR 200",
            body="Backfill PR body",
            head_ref="feature/backfill",
            head_sha="backfill_head_sha_9999",
            base_ref="main",
            base_sha="backfill_base_sha_0000",
            is_merged=False,
            is_closed=False,
            html_url="https://github.com/owner-j/repo-j/pull/200",
        )
    ]

    monkeypatch.setattr(GitHubRepositoryProvider, "list_issues", lambda self, *args, **kwargs: mock_issues)
    monkeypatch.setattr(GitHubRepositoryProvider, "list_pull_requests", lambda self, *args, **kwargs: mock_prs)

    class DummyAuthService:
        base_url = "https://api.github.com"

    service = GitHubInstallationService(auth_service=DummyAuthService())
    result = service.sync_repository_engineering_objects(db, repo)

    assert result["issues"] == 1
    assert result["pull_requests"] == 1

    # Verify Issue
    db_issue = db.scalar(select(Issue).where(Issue.repository_id == repo.id, Issue.github_issue_number == 100))
    assert db_issue is not None
    assert db_issue.source_type == "human"
    assert db_issue.agent_id is None
    assert db_issue.task_id is None

    # Verify PR
    db_pr = db.scalar(select(PullRequest).where(PullRequest.repository_id == repo.id, PullRequest.title == "Backfill PR 200"))
    assert db_pr is not None
    assert db_pr.source_commit == "backfill_head_sha_9999"
    db_change = db.scalar(select(Change).where(Change.id == db_pr.source_change_id))
    assert db_change is not None
    meta = json.loads(db_change.metadata_json)
    assert meta["source"] == "github"
    assert "agent_id" not in meta or meta["agent_id"] is None
