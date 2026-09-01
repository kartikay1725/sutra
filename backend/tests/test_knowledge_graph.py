import pytest
from uuid import uuid4

from app.models.repository import Repository
from app.models.user import User
from app.core.security import hash_password


def make_user(db, user_id="kg-user"):
    user = User(
        id=user_id,
        username=f"user-{user_id}",
        email=f"{user_id}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, user)

    return user
def make_repo(db, owner_id, repo_name="kg-repo"):
    repo = Repository(
        owner_id=owner_id,
        name=repo_name,
        slug=repo_name,
        description="test repo",
        storage_key="test-storage-key",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def test_knowledge_graph_endpoints(client, db):
    user = make_user(db)
    repo = make_repo(db, user.id)
    
    login_resp = client.post(
        "/v1/auth/login",
        json={"login": user.email, "password": "password"},
    )
    user_token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {user_token}"}
    
    # 1. Upsert node A (File)
    resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/graph/nodes",
        headers=auth_headers,
        json={
            "entity_type": "file",
            "name": "app/main.py",
            "summary": "Main FastAPI entrypoint",
            "metadata_json": {"language": "python"}
        }
    )
    assert resp.status_code == 201
    node_a = resp.json()
    assert node_a["name"] == "app/main.py"
    
    # 2. Upsert node B (Class)
    resp2 = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/graph/nodes",
        headers=auth_headers,
        json={
            "entity_type": "class",
            "name": "User",
            "summary": "User model",
        }
    )
    assert resp2.status_code == 201
    node_b = resp2.json()
    
    # 3. Add edge (A imports B)
    edge_resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/graph/edges",
        headers=auth_headers,
        json={
            "source_node_id": node_a["id"],
            "target_node_id": node_b["id"],
            "relationship_type": "imports"
        }
    )
    assert edge_resp.status_code == 201
    assert edge_resp.json()["relationship_type"] == "imports"
    
    # 4. Search
    search_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/graph/search?q=FastAPI",
        headers=auth_headers,
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert len(search_data) == 1
    assert search_data[0]["id"] == node_a["id"]
    
    # 5. Get Subgraph for Node A
    subgraph_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/graph/nodes/{node_a['id']}",
        headers=auth_headers,
    )
    assert subgraph_resp.status_code == 200
    subgraph = subgraph_resp.json()
    assert subgraph["node"]["id"] == node_a["id"]
    assert len(subgraph["outgoing_edges"]) == 1
    assert len(subgraph["incoming_edges"]) == 0
    assert node_b["id"] in subgraph["neighbors"]
