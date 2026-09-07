from app.api import environments
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.issue import Issue
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User


def make_user(db, suffix: str | None = None) -> User:
    suffix = suffix or uuid4().hex[:8]

    user = User(
        id=str(uuid4()),
        username=f"issue_agent_user_{suffix}",
        email=f"issue_agent_{suffix}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def make_agent(db, owner: User, name: str = "Atlas") -> Agent:
    agent = Agent(
        id=str(uuid4()),
        owner_id=owner.id,
        name=name,
        description="Agent Issue API test agent",
        provider="test",
        model="test-model",
        token_hash=hash_password(f"agent-token-{uuid4().hex}"),
        token_prefix=uuid4().hex[:16],
        status="active",
        is_active=True,
    )

    db.add(agent)
    db.flush()

    # SUTRA uses the agent ID as its Actor identity.
    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=owner.id,
        capabilities=(
            '["repository.read","repository.write",'
            '"change.create","change.commit"]'
        ),
    )

    db.add(actor)
    db.flush()

    return agent


def make_session(db, agent: Agent):
    raw_token = f"sutra_session_{uuid4().hex}_{uuid4().hex}"

    session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:32],
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        last_seen_at=datetime.now(timezone.utc),
    )

    db.add(session)
    db.flush()

    return session, raw_token


def make_repository(db, owner: User) -> Repository:
    repository = Repository(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"agent-issue-repo-{uuid4().hex[:8]}",
        slug=f"agent-issue-repo-{uuid4().hex[:8]}",
        description="Agent Issue API test repository",
        visibility="private",
        storage_key=f"test/{uuid4().hex}",
        provider_type="github",
        provider_owner="kartikay1725",
        external_id=str(900000000 + int(uuid4().hex[:6], 16)),
        github_installation_id=158557464,
        default_branch="master",
        settings={},
    )

    db.add(repository)
    db.flush()

    return repository


def make_task(
    db,
    owner: User,
    repository: Repository,
    agent: Agent,
    session: AgentSession,
    *,
    claimed: bool = True,
) -> Task:
    task = Task(
        id=str(uuid4()),
        repository_id=repository.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        assigned_user_id=None,
        claimed_by_session_id=session.id if claimed else None,
        lease_expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=1)
            if claimed
            else None
        ),
        resulting_change_id=None,
        resulting_pull_request_id=None,
        title=f"Agent issue task {uuid4().hex[:8]}",
        description="Create an issue from an authenticated agent session.",
        status=Task.STATUS_IN_PROGRESS if claimed else Task.STATUS_ASSIGNED,
        priority=Task.PRIORITY_MEDIUM,
        priority_index=0.0,
        task_type=Task.TYPE_FEATURE,
        source="test",
    )

    db.add(task)
    db.flush()

    return task


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def fake_github_provider(monkeypatch):
    """
    Replace the real GitHub provider used by the API with a deterministic
    in-memory provider. This test therefore exercises:

        AgentSession -> Task authorization -> AgentIssueService -> API

    without creating real GitHub issues.
    """
    from app.api import agent_issues
    from app.providers.base import ProviderIssue

    created: list[ProviderIssue] = []

    class FakeGitHubProvider:
        def __init__(self, *args, **kwargs):
            pass

        def create_issue(self, owner, name, title, body):
            issue = ProviderIssue(
            id=123456,
            number=42,
            title=title,
            body=body,
            state="open",
            author_login="sutra[bot]",
            author_name="SUTRA",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            closed_at=None,
            labels=[],
            html_url="https://github.com/kartikey1725/test/issues/42",
        )
            created.append(issue)
            return issue

    monkeypatch.setattr(
        agent_issues,
        "GitHubRepositoryProvider",
        FakeGitHubProvider,
    )

    return created


def test_valid_agent_session_can_create_agent_issue(
    client,
    db,
    monkeypatch,
):
    created = fake_github_provider(monkeypatch)

    owner = make_user(db)
    agent = make_agent(db, owner, name="Atlas")
    session, token = make_session(db, agent)
    repository = make_repository(db, owner)
    task = make_task(
        db,
        owner,
        repository,
        agent,
        session,
        claimed=True,
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/issues",
        headers=bearer(token),
        json={
            "title": "Database connection failure",
            "body": "The database connection pool is exhausted.",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["title"] == "[Agent: Atlas] Database connection failure"
    assert data["github_issue_number"] == 42
    assert data["status"] == "open"
    assert data["source_type"] == "agent"
    assert data["agent_id"] == agent.id
    assert data["agent_session_id"] == session.id
    assert data["task_id"] == task.id

    assert len(created) == 1

    github_issue = created[0]

    assert github_issue.title == "[Agent: Atlas] Database connection failure"

    assert "**Agent:** Atlas" in github_issue.body
    assert f"**Agent ID:** `{agent.id}`" in github_issue.body
    assert f"**Session ID:** `{session.id}`" in github_issue.body
    assert f"**Task ID:** `{task.id}`" in github_issue.body
    assert "The database connection pool is exhausted." in github_issue.body

    stored_issue = db.query(Issue).filter(
        Issue.github_issue_number == 42,
        Issue.repository_id == repository.id,
    ).one()

    assert stored_issue.source_type == "agent"
    assert stored_issue.agent_id == agent.id
    assert stored_issue.agent_session_id == session.id
    assert stored_issue.task_id == task.id
    assert stored_issue.author_id == agent.id
    assert stored_issue.github_issue_number == 42


def test_wrong_agent_cannot_create_issue(
    client,
    db,
    monkeypatch,
):
    fake_github_provider(monkeypatch)

    owner = make_user(db)

    assigned_agent = make_agent(
        db,
        owner,
        name="Atlas",
    )

    wrong_agent = make_agent(
        db,
        owner,
        name="Orion",
    )

    wrong_session, wrong_token = make_session(
        db,
        wrong_agent,
    )

    repository = make_repository(
        db,
        owner,
    )

    # Task belongs to Atlas, but request comes from Orion.
    task = make_task(
        db,
        owner,
        repository,
        assigned_agent,
        wrong_session,
        claimed=False,
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/issues",
        headers=bearer(wrong_token),
        json={
            "title": "Unauthorized issue",
            "body": "This must not be created.",
        },
    )

    assert response.status_code == 403
    assert "assigned to" in response.json()["detail"].lower()


def test_wrong_session_cannot_create_issue(
    client,
    db,
    monkeypatch,
):
    fake_github_provider(monkeypatch)

    owner = make_user(db)

    agent = make_agent(
        db,
        owner,
        name="Atlas",
    )

    legitimate_session, legitimate_token = make_session(
        db,
        agent,
    )

    wrong_session, wrong_token = make_session(
        db,
        agent,
    )

    repository = make_repository(
        db,
        owner,
    )

    # Task is claimed by legitimate_session.
    task = make_task(
        db,
        owner,
        repository,
        agent,
        legitimate_session,
        claimed=True,
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/issues",
        headers=bearer(wrong_token),
        json={
            "title": "Wrong session issue",
            "body": "This must not be created.",
        },
    )

    assert response.status_code == 403
    assert "session" in response.json()["detail"].lower()

    # Make sure the legitimate session itself remains usable.
    response2 = client.post(
        f"/v1/agent/tasks/{task.id}/issues",
        headers=bearer(legitimate_token),
        json={
            "title": "Legitimate issue",
            "body": "This one is authorized.",
        },
    )

    assert response2.status_code == 201


def test_unclaimed_task_cannot_create_issue(
    client,
    db,
    monkeypatch,
):
    fake_github_provider(monkeypatch)

    owner = make_user(db)

    agent = make_agent(
        db,
        owner,
        name="Atlas",
    )

    session, token = make_session(
        db,
        agent,
    )

    repository = make_repository(
        db,
        owner,
    )

    # assigned to the agent, but NOT claimed by this session.
    task = make_task(
        db,
        owner,
        repository,
        agent,
        session,
        claimed=False,
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/issues",
        headers=bearer(token),
        json={
            "title": "Unclaimed task issue",
            "body": "This must not be created.",
        },
    )

    assert response.status_code == 403
    assert "task lease" in response.json()["detail"].lower()


def test_missing_agent_authentication_is_rejected(
    client,
    db,
):
    owner = make_user(db)
    agent = make_agent(db, owner, name="Atlas")
    session, _ = make_session(db, agent)
    repository = make_repository(db, owner)

    task = make_task(
        db,
        owner,
        repository,
        agent,
        session,
        claimed=True,
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/issues",
        json={
            "title": "Unauthenticated issue",
            "body": "This must not be created.",
        },
    )

    assert response.status_code == 401

