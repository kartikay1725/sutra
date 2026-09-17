import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.user import User
from app.models.actor import Actor
from app.models.repository import Repository
from app.models.task import Task
from app.models.pull_request import PullRequest
from app.models.issue import Issue
from app.models.change import Change
from app.core.security import create_access_token


def _create_user_and_auth(db: Session, username: str) -> tuple[User, dict]:
    user_id = str(uuid4())
    actor = Actor(id=user_id, type="user", name=username, owner_id=user_id, capabilities="[]")
    db.add(actor)
    user = User(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        password_hash="hashed_pw",
    )
    db.add(user)
    db.commit()
    token = create_access_token(user_id)
    return user, {"Authorization": f"Bearer {token}"}


def _create_repo(db: Session, owner: User, name: str, visibility: str = "private") -> Repository:
    repo = Repository(
        id=str(uuid4()),
        owner_id=owner.id,
        name=name,
        slug=name.lower(),
        description=f"Description for {name}",
        visibility=visibility,
        default_branch="main",
        storage_key=str(uuid4()),
        connection_type="owned",
    )
    db.add(repo)
    db.commit()
    return repo


def test_repository_search_by_name(client: TestClient, db: Session):
    # Setup test users
    user_a, headers_a = _create_user_and_auth(db, f"user_a_{uuid4().hex[:8]}")
    user_b, headers_b = _create_user_and_auth(db, f"user_b_{uuid4().hex[:8]}")

    # Create repos for user A
    repo_dam = _create_repo(db, user_a, "dam-project", "private")
    repo_sutra = _create_repo(db, user_a, "sutra-core", "private")
    repo_other = _create_repo(db, user_a, "other-service", "private")

    # Create repo for user B
    repo_b_dam = _create_repo(db, user_b, "dam-secret", "private")

    # 1. Exact name match
    res = client.get("/v1/repositories?q=dam-project", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "dam-project"
    assert data[0]["owner"] == user_a.username
    assert data[0]["visibility"] == "private"
    assert data[0]["default_branch"] == "main"

    # 2. Case-insensitive partial matching (example from spec: "dam" matches "dam-project")
    res = client.get("/v1/repositories?q=DAM", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "dam-project"

    # 3. Partial matching "sutra" matches "sutra-core"
    res = client.get("/v1/repositories?q=sutra", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "sutra-core"

    # 4. No matches
    res = client.get("/v1/repositories?q=nonexistent-repo-xyz", headers=headers_a)
    assert res.status_code == 200
    assert res.json() == []

    # 5. Empty search restores all owned repositories
    res = client.get("/v1/repositories", headers=headers_a)
    assert res.status_code == 200
    names = {r["name"] for r in res.json()}
    assert "dam-project" in names
    assert "sutra-core" in names
    assert "other-service" in names
    assert "dam-secret" not in names  # User B's repo must NOT be listed

    # 6. Authorization Isolation: User A cannot see User B's private repo through search
    res = client.get("/v1/repositories?q=dam-secret", headers=headers_a)
    assert res.status_code == 200
    assert res.json() == []

    # User B searching "dam" only sees User B's repo
    res = client.get("/v1/repositories?q=dam", headers=headers_b)
    assert res.status_code == 200
    data_b = res.json()
    assert len(data_b) == 1
    assert data_b[0]["name"] == "dam-secret"


def test_global_search_isolation(client: TestClient, db: Session):
    user_a, headers_a = _create_user_and_auth(db, f"user_ga_{uuid4().hex[:8]}")
    user_b, headers_b = _create_user_and_auth(db, f"user_gb_{uuid4().hex[:8]}")

    # Private repo for User A
    repo_priv = _create_repo(db, user_a, f"priv-{uuid4().hex[:6]}", "private")
    # Public repo for User A
    repo_pub = _create_repo(db, user_a, f"pub-{uuid4().hex[:6]}", "public")

    # Task in private repo
    task_priv = Task(
        id=str(uuid4()),
        repository_id=repo_priv.id,
        created_by=user_a.id,
        title=f"Secret Task {uuid4().hex[:6]}",
        status="open",
        priority="high",
        task_type="feature",
        source="human",
    )
    db.add(task_priv)
    db.commit()

    # User B should NOT find User A's private repo or task
    res_b = client.get(f"/v1/search?q={task_priv.title}", headers=headers_b)
    assert res_b.status_code == 200
    assert not any(item["name"] == task_priv.title for item in res_b.json())

    # User A CAN find their own private task
    res_a = client.get(f"/v1/search?q={task_priv.title}", headers=headers_a)
    assert res_a.status_code == 200
    assert any(item["name"] == task_priv.title for item in res_a.json())

    # Public repo is discoverable by both User A and User B
    res_pub_b = client.get(f"/v1/search?q={repo_pub.name}", headers=headers_b)
    assert res_pub_b.status_code == 200
    assert any(item["type"] == "repository" and repo_pub.name in item["name"] for item in res_pub_b.json())


def test_global_search_owner_slash_repo_and_private_access(client: TestClient, db: Session):
    user_owner, headers_owner = _create_user_and_auth(db, f"own_{uuid4().hex[:6]}")
    repo = _create_repo(db, user_owner, f"alpha-repo-{uuid4().hex[:6]}", "private")

    # 1. Owner can search by "owner/repo"
    query_full = f"{user_owner.username}/{repo.name}"
    res = client.get(f"/v1/search?q={query_full}", headers=headers_owner)
    assert res.status_code == 200
    items = res.json()
    assert any(i["type"] == "repository" and i["url"] == f"/repositories/{repo.name}" for i in items)

    # 2. Owner can search by repo name directly and find private repo
    res_name = client.get(f"/v1/search?q={repo.name}", headers=headers_owner)
    assert res_name.status_code == 200
    items_name = res_name.json()
    assert any(i["type"] == "repository" and repo.name in i["name"] for i in items_name)

    # 3. Search by owner username finds user's repos
    res_owner = client.get(f"/v1/search?q={user_owner.username}", headers=headers_owner)
    assert res_owner.status_code == 200
    items_owner = res_owner.json()
    assert any(i["type"] == "repository" and repo.name in i["name"] for i in items_owner)


def test_search_prs_issues_changes(client: TestClient, db: Session):
    user_owner, headers_owner = _create_user_and_auth(db, f"owner_{uuid4().hex[:6]}")
    user_other, headers_other = _create_user_and_auth(db, f"other_{uuid4().hex[:6]}")
    repo_priv = _create_repo(db, user_owner, f"priv-box-{uuid4().hex[:6]}", "private")

    # 1. Create a change
    change = Change(
        id=str(uuid4()),
        repository_id=repo_priv.id,
        actor_id=user_owner.id,
        intent=f"Refactor core payment gateway logic {uuid4().hex[:6]}",
        status="proposed",
        operation_key=str(uuid4()),
    )
    db.add(change)

    # 2. Create a pull request linked to the change
    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo_priv.id,
        author_id=user_owner.id,
        source_change_id=change.id,
        title=f"feat(payments): unified checkout session {uuid4().hex[:6]}",
        description="Implements PCI-compliant tokenized flows",
        target_branch="main",
        status="open",
    )
    db.add(pr)

    # 3. Create an issue with an explicit issue number
    issue = Issue(
        id=str(uuid4()),
        repository_id=repo_priv.id,
        github_issue_number=9942,
        title=f"Memory leak in telemetry collector {uuid4().hex[:6]}",
        body="Observed 500MB leak after long-running sessions",
        status="open",
        source_type="human",
        actor_id=user_owner.id,
    )
    db.add(issue)
    db.commit()

    # Unauthorized user should NOT find private PR, Issue, or Change
    res_other = client.get(f"/v1/search?q={pr.title}", headers=headers_other)
    assert res_other.status_code == 200
    assert not any(i["name"] == pr.title for i in res_other.json())

    res_other_issue = client.get("/v1/search?q=9942", headers=headers_other)
    assert res_other_issue.status_code == 200
    assert not any("9942" in i["name"] for i in res_other_issue.json())

    # Authorized owner CAN find their PR by title
    res_pr = client.get(f"/v1/search?q={pr.title}", headers=headers_owner)
    assert res_pr.status_code == 200
    assert any(i["type"] == "pull_request" and i["name"] == pr.title for i in res_pr.json())

    # Authorized owner CAN find their Change by intent keyword
    res_change = client.get(f"/v1/search?q=payment gateway", headers=headers_owner)
    assert res_change.status_code == 200
    assert any(i["type"] == "change" and change.intent in i["name"] for i in res_change.json())

    # Authorized owner CAN find their Issue by number "#9942"
    res_hash_issue = client.get("/v1/search?q=%239942", headers=headers_owner)
    assert res_hash_issue.status_code == 200
    assert any(i["type"] == "issue" and "#9942" in i["name"] for i in res_hash_issue.json())

    # Authorized owner CAN find their Issue by title
    res_title_issue = client.get(f"/v1/search?q={issue.title}", headers=headers_owner)
    assert res_title_issue.status_code == 200
    assert any(i["type"] == "issue" and issue.title in i["name"] for i in res_title_issue.json())


