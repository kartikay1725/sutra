import uuid
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_dependency import ChangeDependency
from app.models.repository import Repository
from app.models.user import User


def make_user(
    db,
    user_id=None,
    username=None,
    email=None,
):
    user_id = user_id or str(uuid.uuid4())
    username = username or f"user-{uuid.uuid4().hex[:8]}"
    email = email or f"{username}@example.com"

    user = User(
        id=user_id,
        username=username,
        email=email,
        password_hash=hash_password("test-password"),
    )

    db.add(user)
    db.flush()

    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, user)

    return user


def make_repository(
    db: Session,
    owner_id: str,
    repository_id: str | None = None,
) -> Repository:
    repository_id = repository_id or f"repo-{uuid.uuid4().hex[:8]}"

    repository = Repository(
        id=repository_id,
        owner_id=owner_id,
        name=repository_id,
        slug=repository_id.lower(),
        description="Test repository",
        visibility="private",
        default_branch="main",
        storage_key=f"{repository_id}.git",
    )

    db.add(repository)
    db.flush()

    return repository


def make_actor(
    db,
    owner_id,
    actor_id=None,
):
    actor = Actor(
        id=actor_id or str(uuid.uuid4()),
        type="agent",
        name=f"agent-{uuid.uuid4().hex[:8]}",
        owner_id=owner_id,
        capabilities='["repository.read","change.create"]',
    )

    db.add(actor)
    db.flush()

    return actor


def make_change(
    db,
    repository_id,
    actor_id,
    change_id=None,
    intent="Test change",
    status="recorded",
    risk_level="low",
    resulting_commit=None,
):
    change = Change(
        id=change_id or str(uuid.uuid4()),
        repository_id=repository_id,
        actor_id=actor_id,
        intent=intent,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        resulting_commit=resulting_commit,
        status=status,
        risk_level=risk_level,
        metadata_json="{}",
    )

    db.add(change)
    db.flush()

    return change


def auth_headers(user: User):
    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


def dependency_payload(
    target_change_id,
    relationship="depends_on",
    reason="Test dependency",
):
    return {
        "target_change_id": target_change_id,
        "relationship": relationship,
        "reason": reason,
    }


def test_create_depends_on_dependency(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            target.id,
            "depends_on",
            "Source depends on target",
        ),
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["source_change_id"] == source.id
    assert data["target_change_id"] == target.id
    assert data["relationship"] == "depends_on"
    assert data["reason"] == "Source depends on target"
    assert data["id"]


@pytest.mark.parametrize(
    "relationship",
    [
        "conflicts_with",
        "supersedes",
        "derived_from",
    ],
)
def test_create_other_supported_relationships(
    client: TestClient,
    db,
    relationship,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            target.id,
            relationship,
        ),
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["relationship"] == relationship
    assert data["source_change_id"] == source.id
    assert data["target_change_id"] == target.id


def test_create_dependency_without_reason(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json={
            "target_change_id": target.id,
            "relationship": "depends_on",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201
    assert response.json()["reason"] is None


def test_self_dependency_is_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{change.id}/dependencies",
        json=dependency_payload(change.id),
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "A change cannot depend on itself"
    )


def test_cross_repository_dependency_is_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)

    repository_one = make_repository(
        db,
        user.id,
    )
    repository_two = make_repository(
        db,
        user.id,
    )

    actor_one = make_actor(
        db,
        user.id,
    )

    source = make_change(
        db,
        repository_one.id,
        actor_one.id,
    )
    target = make_change(
        db,
        repository_two.id,
        actor_one.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(target.id),
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Changes must belong to the same repository"
    )


def test_duplicate_dependency_is_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    first = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(target.id),
        headers=auth_headers(user),
    )

    assert first.status_code == 201

    second = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(target.id),
        headers=auth_headers(user),
    )

    assert second.status_code == 409
    assert (
        second.json()["detail"]
        == "This dependency already exists"
    )


def test_unsupported_relationship_is_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json={
            "target_change_id": target.id,
            "relationship": "invalid_relationship",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_dependency_cycle_is_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    change_a = make_change(
        db,
        repository.id,
        actor.id,
        intent="Change A",
    )
    change_b = make_change(
        db,
        repository.id,
        actor.id,
        intent="Change B",
    )
    change_c = make_change(
        db,
        repository.id,
        actor.id,
        intent="Change C",
    )

    db.commit()

    headers = auth_headers(user)

    response_ab = client.post(
        f"/v1/changes/{change_a.id}/dependencies",
        json=dependency_payload(
            change_b.id,
            "depends_on",
        ),
        headers=headers,
    )

    assert response_ab.status_code == 201

    response_bc = client.post(
        f"/v1/changes/{change_b.id}/dependencies",
        json=dependency_payload(
            change_c.id,
            "depends_on",
        ),
        headers=headers,
    )

    assert response_bc.status_code == 201

    response_ca = client.post(
        f"/v1/changes/{change_c.id}/dependencies",
        json=dependency_payload(
            change_a.id,
            "depends_on",
        ),
        headers=headers,
    )

    assert response_ca.status_code == 409
    assert (
        response_ca.json()["detail"]
        == "Dependency would create a cycle"
    )


def test_non_dependency_relationship_does_not_trigger_cycle_check(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    change_a = make_change(
        db,
        repository.id,
        actor.id,
    )
    change_b = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    headers = auth_headers(user)

    first = client.post(
        f"/v1/changes/{change_a.id}/dependencies",
        json=dependency_payload(
            change_b.id,
            "conflicts_with",
        ),
        headers=headers,
    )

    assert first.status_code == 201

    second = client.post(
        f"/v1/changes/{change_b.id}/dependencies",
        json=dependency_payload(
            change_a.id,
            "conflicts_with",
        ),
        headers=headers,
    )

    assert second.status_code == 201


def test_list_dependencies_returns_related_edges(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target_one = make_change(
        db,
        repository.id,
        actor.id,
    )
    target_two = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    headers = auth_headers(user)

    first = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            target_one.id,
            "depends_on",
            "First dependency",
        ),
        headers=headers,
    )

    second = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            target_two.id,
            "derived_from",
            "Second dependency",
        ),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        f"/v1/changes/{source.id}/dependencies",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert {
        item["target_change_id"]
        for item in data
    } == {
        target_one.id,
        target_two.id,
    }


def test_list_dependencies_includes_edges_where_change_is_target(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    headers = auth_headers(user)

    create_response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            target.id,
            "depends_on",
        ),
        headers=headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/v1/changes/{target.id}/dependencies",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["source_change_id"] == source.id
    assert data[0]["target_change_id"] == target.id


def test_graph_returns_nodes_edges_and_topological_order(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    root = make_change(
        db,
        repository.id,
        actor.id,
        intent="Root",
    )
    middle = make_change(
        db,
        repository.id,
        actor.id,
        intent="Middle",
    )
    leaf = make_change(
        db,
        repository.id,
        actor.id,
        intent="Leaf",
    )

    db.commit()

    headers = auth_headers(user)

    first = client.post(
        f"/v1/changes/{root.id}/dependencies",
        json=dependency_payload(
            middle.id,
            "depends_on",
        ),
        headers=headers,
    )

    second = client.post(
        f"/v1/changes/{middle.id}/dependencies",
        json=dependency_payload(
            leaf.id,
            "depends_on",
        ),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        f"/v1/changes/{root.id}/graph?depth=3",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["root_change_id"] == root.id
    assert data["depth"] == 3

    node_ids = {
        node["id"]
        for node in data["nodes"]
    }

    assert node_ids == {
        root.id,
        middle.id,
        leaf.id,
    }

    assert len(data["edges"]) == 2

    edge_pairs = {
        (
            edge["source_change_id"],
            edge["target_change_id"],
        )
        for edge in data["edges"]
    }

    assert edge_pairs == {
        (root.id, middle.id),
        (middle.id, leaf.id),
    }

    ordering = data["topological_order"]

    assert set(ordering) == {
        root.id,
        middle.id,
        leaf.id,
    }

    assert ordering.index(root.id) < ordering.index(middle.id)
    assert ordering.index(middle.id) < ordering.index(leaf.id)


def test_graph_depth_limits_traversal(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    root = make_change(
        db,
        repository.id,
        actor.id,
    )
    middle = make_change(
        db,
        repository.id,
        actor.id,
    )
    leaf = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    headers = auth_headers(user)

    first = client.post(
        f"/v1/changes/{root.id}/dependencies",
        json=dependency_payload(
            middle.id,
            "depends_on",
        ),
        headers=headers,
    )

    second = client.post(
        f"/v1/changes/{middle.id}/dependencies",
        json=dependency_payload(
            leaf.id,
            "depends_on",
        ),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        f"/v1/changes/{root.id}/graph?depth=1",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert {
        node["id"]
        for node in data["nodes"]
    } == {
        root.id,
        middle.id,
    }

    assert len(data["edges"]) == 1
    assert data["edges"][0]["target_change_id"] == middle.id


@pytest.mark.parametrize(
    "depth",
    [0, -1, 21, 100],
)
def test_graph_rejects_invalid_depth(
    client: TestClient,
    db,
    depth,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/graph?depth={depth}",
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Depth must be between 1 and 20"
    )


def test_dependency_endpoint_requires_authentication(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(target.id),
    )

    assert response.status_code == 401


def test_dependency_listing_requires_authentication(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/dependencies",
    )

    assert response.status_code == 401


def test_graph_endpoint_requires_authentication(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/graph",
    )

    assert response.status_code == 401


def test_other_user_cannot_create_dependency_on_owned_changes(
    client: TestClient,
    db,
):
    owner = make_user(
        db,
        user_id="dependency-owner",
        username="dependency-owner",
        email="dependency-owner@example.com",
    )

    other_user = make_user(
        db,
        user_id="dependency-other",
        username="dependency-other",
        email="dependency-other@example.com",
    )

    repository = make_repository(
        db,
        owner.id,
    )
    actor = make_actor(
        db,
        owner.id,
    )

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(target.id),
        headers=auth_headers(other_user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_other_user_cannot_list_dependencies(
    client: TestClient,
    db,
):
    owner = make_user(
        db,
        user_id="list-owner",
        username="list-owner",
        email="list-owner@example.com",
    )

    other_user = make_user(
        db,
        user_id="list-other",
        username="list-other",
        email="list-other@example.com",
    )

    repository = make_repository(
        db,
        owner.id,
    )
    actor = make_actor(
        db,
        owner.id,
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/dependencies",
        headers=auth_headers(other_user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_other_user_cannot_read_graph(
    client: TestClient,
    db,
):
    owner = make_user(
        db,
        user_id="graph-owner",
        username="graph-owner",
        email="graph-owner@example.com",
    )

    other_user = make_user(
        db,
        user_id="graph-other",
        username="graph-other",
        email="graph-other@example.com",
    )

    repository = make_repository(
        db,
        owner.id,
    )
    actor = make_actor(
        db,
        owner.id,
    )

    change = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.get(
        f"/v1/changes/{change.id}/graph",
        headers=auth_headers(other_user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_dependency_references_nonexistent_change_are_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            str(uuid.uuid4()),
        ),
        headers=auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_graph_unknown_change_is_rejected(
    client: TestClient,
    db,
):
    user = make_user(db)

    db.commit()

    response = client.get(
        f"/v1/changes/{uuid.uuid4()}/graph",
        headers=auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Change not found"


def test_dependency_is_persisted_in_database(
    client: TestClient,
    db,
):
    user = make_user(db)
    repository = make_repository(db, user.id)
    actor = make_actor(db, user.id)

    source = make_change(
        db,
        repository.id,
        actor.id,
    )
    target = make_change(
        db,
        repository.id,
        actor.id,
    )

    db.commit()

    response = client.post(
        f"/v1/changes/{source.id}/dependencies",
        json=dependency_payload(
            target.id,
            "depends_on",
            "Persist this edge",
        ),
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    dependency_id = response.json()["id"]

    dependency = db.get(
        ChangeDependency,
        dependency_id,
    )

    assert dependency is not None
    assert dependency.source_change_id == source.id
    assert dependency.target_change_id == target.id
    assert dependency.relationship == "depends_on"
    assert dependency.reason == "Persist this edge"