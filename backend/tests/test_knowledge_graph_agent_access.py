import json
from datetime import datetime, timezone
from uuid import uuid4

from app.api.agent_dependencies import create_agent_session
from app.core.security import hash_password
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.repository import Repository
from app.models.user import User


def make_user(db):
    user_id = str(uuid4())

    user = User(
        id=user_id,
        username=f"kg-agent-owner-{user_id[:8]}",
        email=f"kg-agent-{user_id[:8]}@example.com",
        password_hash=hash_password("password"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, user)

    return user


def make_repo(db, user):
    repo = Repository(
        owner_id=user.id,
        name="kg-agent-repo",
        slug="kg-agent-repo",
        description="Agent KG integration test repository",
        storage_key=f"kg-agent-storage-{uuid4()}",
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    return repo


def make_agent(db, user):
    agent_id = str(uuid4())

    raw_agent_token = (
        "sutra_agent_test_"
        + uuid4().hex
    )

    agent = Agent(
        id=agent_id,
        owner_id=user.id,
        name=f"KG Agent {agent_id[:8]}",
        description="Knowledge Graph integration test agent",
        token_hash=hash_password(
            raw_agent_token
        ),
        token_prefix=raw_agent_token[:16],
        status="active",
        is_active=True,
    )

    db.add(agent)

    # The agent authorization system expects an Actor
    # representing the agent.
    actor = Actor(
        id=agent.id,
        owner_id=agent.owner_id,
        type="agent",
        name=agent.name,
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
                "knowledge_graph.read",
                "knowledge_graph.write",
            ]
        ),
    )

    db.add(actor)

    db.commit()
    db.refresh(agent)

    return agent


def grant_kg_access(
    db,
    agent,
    repo,
    permissions,
):
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions=json.dumps(
            permissions
        ),
        enabled=True,
    )

    db.add(access)
    db.commit()
    db.refresh(access)

    return access


def make_agent_session(
    db,
    agent,
):
    session, raw_token = create_agent_session(
        agent,
        db,
    )

    return session, raw_token


def test_agent_can_read_and_write_knowledge_graph(
    client,
    db,
):
    user = make_user(db)
    repo = make_repo(db, user)
    agent = make_agent(db, user)

    grant_kg_access(
        db,
        agent,
        repo,
        [
            "repository.read",
            "repository.write",
            "knowledge_graph.read",
            "knowledge_graph.write",
        ],
    )

    session, session_token = make_agent_session(
        db,
        agent,
    )

    assert session.status == "active"

    headers = {
        "Authorization": f"Bearer {session_token}",
    }

    base_url = (
        f"/v1/repositories/"
        f"{user.username}/"
        f"{repo.name}/graph"
    )

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    graph_response = client.get(
        base_url,
        headers=headers,
    )

    assert graph_response.status_code == 200
    assert graph_response.json()["nodes"] == []

    # ------------------------------------------------------------------
    # WRITE NODE
    # ------------------------------------------------------------------

    node_response = client.post(
        f"{base_url}/nodes",
        headers=headers,
        json={
            "entity_type": "file",
            "name": "agent/generated.py",
            "summary": "Created by the connected agent",
            "metadata_json": {
                "source": "agent",
            },
        },
    )

    assert node_response.status_code == 201

    node = node_response.json()

    assert node["name"] == "agent/generated.py"
    assert node["entity_type"] == "file"

    # ------------------------------------------------------------------
    # READ AGAIN
    # ------------------------------------------------------------------

    graph_response_2 = client.get(
        base_url,
        headers=headers,
    )

    assert graph_response_2.status_code == 200

    nodes = graph_response_2.json()["nodes"]

    assert len(nodes) == 1
    assert nodes[0]["id"] == node["id"]

    # ------------------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------------------

    search_response = client.get(
        f"{base_url}/search",
        params={"q": "generated"},
        headers=headers,
    )

    assert search_response.status_code == 200

    search_results = search_response.json()

    assert len(search_results) == 1
    assert search_results[0]["id"] == node["id"]


def test_agent_without_knowledge_graph_write_is_denied(
    client,
    db,
):
    user = make_user(db)
    repo = make_repo(db, user)
    agent = make_agent(db, user)

    grant_kg_access(
        db,
        agent,
        repo,
        [
            "repository.read",
            "knowledge_graph.read",
        ],
    )

    _, session_token = make_agent_session(
        db,
        agent,
    )

    headers = {
        "Authorization": f"Bearer {session_token}",
    }

    base_url = (
        f"/v1/repositories/"
        f"{user.username}/"
        f"{repo.name}/graph"
    )

    # Read must work.
    read_response = client.get(
        base_url,
        headers=headers,
    )

    assert read_response.status_code == 200

    # Write must be denied because this agent
    # has no knowledge_graph.write permission.
    write_response = client.post(
        f"{base_url}/nodes",
        headers=headers,
        json={
            "entity_type": "file",
            "name": "forbidden.py",
        },
    )

    assert write_response.status_code == 403


def test_agent_without_repository_grant_is_denied(
    client,
    db,
):
    user = make_user(db)
    repo = make_repo(db, user)
    agent = make_agent(db, user)

    # Intentionally no AgentRepositoryAccess row.

    _, session_token = make_agent_session(
        db,
        agent,
    )

    headers = {
        "Authorization": f"Bearer {session_token}",
    }

    base_url = (
        f"/v1/repositories/"
        f"{user.username}/"
        f"{repo.name}/graph"
    )

    response = client.get(
        base_url,
        headers=headers,
    )

    assert response.status_code == 404


def test_agent_graph_read_without_repo_grant_on_private_repo_returns_404(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="private-repo-no-grant",
        slug="private-repo-no-grant",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()
    agent = make_agent(db, user)
    _, session_token = make_agent_session(db, agent)
    headers = {"Authorization": f"Bearer {session_token}"}
    base_url = f"/v1/repositories/{user.username}/{repo.name}/graph"

    resp = client.get(base_url, headers=headers)
    assert resp.status_code == 404

    resp = client.get(f"{base_url}/search?q=test", headers=headers)
    assert resp.status_code == 404

    resp = client.get(f"{base_url}/nodes/some-node-id", headers=headers)
    assert resp.status_code == 404


def test_agent_graph_read_with_repo_grant_on_private_repo_allowed(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="private-repo-grant",
        slug="private-repo-grant",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()
    agent = make_agent(db, user)
    grant_kg_access(db, agent, repo, ["knowledge_graph.read"])
    _, session_token = make_agent_session(db, agent)
    headers = {"Authorization": f"Bearer {session_token}"}
    base_url = f"/v1/repositories/{user.username}/{repo.name}/graph"

    resp = client.get(base_url, headers=headers)
    assert resp.status_code == 200


def test_agent_graph_read_with_repo_grant_but_no_kg_read_capability_denied(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="private-repo-grant-no-kg-read",
        slug="private-repo-grant-no-kg-read",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()
    agent = make_agent(db, user)
    grant_kg_access(db, agent, repo, ["repository.read"])
    _, session_token = make_agent_session(db, agent)
    headers = {"Authorization": f"Bearer {session_token}"}
    base_url = f"/v1/repositories/{user.username}/{repo.name}/graph"

    resp = client.get(base_url, headers=headers)
    assert resp.status_code == 403


def test_agent_graph_read_repo_b_with_grant_for_repo_a_denied(client, db):
    user = make_user(db)
    repo_a = Repository(
        owner_id=user.id,
        name="repo-a",
        slug="repo-a",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    repo_b = Repository(
        owner_id=user.id,
        name="repo-b",
        slug="repo-b",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add_all([repo_a, repo_b])
    db.commit()
    agent = make_agent(db, user)
    grant_kg_access(db, agent, repo_a, ["knowledge_graph.read"])
    _, session_token = make_agent_session(db, agent)
    headers = {"Authorization": f"Bearer {session_token}"}

    resp = client.get(f"/v1/repositories/{user.username}/{repo_b.name}/graph", headers=headers)
    assert resp.status_code == 404


def test_agent_session_a_attempt_repo_grant_for_agent_b_denied(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="repo-ab",
        slug="repo-ab",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()
    agent_a = make_agent(db, user)
    agent_b = make_agent(db, user)
    grant_kg_access(db, agent_b, repo, ["knowledge_graph.read"])

    _, session_token_a = make_agent_session(db, agent_a)
    headers = {"Authorization": f"Bearer {session_token_a}"}

    resp = client.get(f"/v1/repositories/{user.username}/{repo.name}/graph", headers=headers)
    assert resp.status_code == 404


def test_public_repository_agent_behavior(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="public-repo",
        slug="public-repo",
        visibility="public",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()
    agent = make_agent(db, user)
    _, session_token = make_agent_session(db, agent)
    headers = {"Authorization": f"Bearer {session_token}"}
    base_url = f"/v1/repositories/{user.username}/{repo.name}/graph"

    resp = client.get(base_url, headers=headers)
    assert resp.status_code == 403


def test_human_legitimate_graph_access(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="human-repo",
        slug="human-repo",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()

    login_resp = client.post(
        "/v1/auth/login",
        json={"login": user.email, "password": "password"},
    )
    user_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {user_token}"}

    resp = client.get(f"/v1/repositories/{user.username}/{repo.name}/graph", headers=headers)
    assert resp.status_code == 200


def test_graph_write_requires_explicit_write_grant(client, db):
    user = make_user(db)
    repo = Repository(
        owner_id=user.id,
        name="write-repo",
        slug="write-repo",
        visibility="private",
        storage_key=f"storage-{uuid4()}"
    )
    db.add(repo)
    db.commit()
    agent = make_agent(db, user)
    grant_kg_access(db, agent, repo, ["knowledge_graph.read"])
    _, session_token = make_agent_session(db, agent)
    headers = {"Authorization": f"Bearer {session_token}"}
    base_url = f"/v1/repositories/{user.username}/{repo.name}/graph"

    resp = client.post(
        f"{base_url}/nodes",
        headers=headers,
        json={"entity_type": "file", "name": "test.py"}
    )
    assert resp.status_code == 403