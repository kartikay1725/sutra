import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.models.user import User
from app.models.repository import Repository
from app.models.task import Task
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.discussion import Discussion
from app.core.security import hash_password
from app.services.repository_service import RepositoryService
from app.services.knowledge_graph_service import index_engineering_lifecycle, get_file_context


def setup_kg_fixtures(db):
    from tests.conftest import ensure_test_actor

    user = User(
        id=str(uuid4()),
        username=f"kg_user_{uuid4().hex[:8]}",
        email=f"kg_user_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"kg_repo_{uuid4().hex[:8]}",
        description="Knowledge Graph Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="Atlas-Graph-Indexer",
        description="Indexes repo entities",
        token_hash=hash_password("agent-token"),
        token_prefix="sutra_agent_t",
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
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(agent_actor)
    db.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        assigned_agent_id=agent.id,
        title="Refactor Token Middleware",
        description="Modify auth middleware to validate tokens",
        status="completed",
    )
    db.add(task)
    db.flush()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent.id,
        status="recorded",
        intent="Update auth/middleware.py to parse JWT headers",
        metadata_json='{"files": ["auth/middleware.py"]}',
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        source_change_id=change.id,
        author_id=agent.id,
        target_branch="main",
        status="merged",
        title="feat: Update auth/middleware.py",
    )
    db.add(pr)
    db.flush()

    task.resulting_change_id = change.id
    task.resulting_pull_request_id = pr.id

    disc = Discussion(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        title=f"[Task: {task.id}] RFC: Token Middleware Security",
        body=f"Task ID: {task.id}\nDiscussion on token handling",
        category="Architecture",
    )
    db.add(disc)
    db.commit()

    return user, repo, task, change, pr, agent, disc


def test_knowledge_graph_lifecycle_indexing_and_queries(client, db):
    user, repo, task, change, pr, agent, disc = setup_kg_fixtures(db)

    # 1. Login user
    login_resp = client.post("/v1/auth/login", json={"login": user.email, "password": "password"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Run engineering lifecycle indexer
    counts = index_engineering_lifecycle(db, repo.id)
    assert counts["nodes"] >= 4
    assert counts["edges"] >= 3

    # 3. Query Graph Data API
    graph_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/graph/data",
        headers=headers,
    )
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()

    node_types = {n["entity_type"] for n in graph_data["nodes"]}
    assert "task" in node_types
    assert "agent" in node_types
    assert "change" in node_types
    assert "pull_request" in node_types
    assert "discussion" in node_types

    edge_types = {e["relationship_type"] for e in graph_data["edges"]}
    assert "assigned_to" in edge_types
    assert "produced" in edge_types
    assert "reviewed_in" in edge_types
    assert "discussed_in" in edge_types

    # 4. Query Context for File
    ctx_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/graph/context?file_path=auth/middleware.py",
        headers=headers,
    )
    assert ctx_resp.status_code == 200
    ctx_data = ctx_resp.json()
    assert ctx_data["file"] == "auth/middleware.py"
    assert len(ctx_data["related_entities"]) >= 1
    rel_names = [r["name"] for r in ctx_data["related_entities"]]
    assert any(change.id[:8] in name for name in rel_names)
