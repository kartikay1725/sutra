from datetime import datetime, timezone
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.main import app
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.organization import (
    Organization,
    OrganizationMember,
)
from app.models.repository import Repository
from app.models.user import User


def _create_human_actor(
    db,
    user: User,
) -> Actor:
    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    db.add(actor)
    db.flush()

    return actor


def test_audit_returns_real_change_event_and_scopes_to_org(
    client,
    db,
):
    user = User(
        id=str(uuid4()),
        username="audit-owner",
        email="audit-owner@example.com",
        password_hash="test",
    )

    db.add(user)
    db.flush()

    user_actor = _create_human_actor(
        db,
        user,
    )

    org = Organization(
        id=str(uuid4()),
        name="audit-org",
        display_name="Audit Org",
    )

    db.add(org)
    db.flush()

    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
    )

    db.add(
        Actor(
            id=org.id,
            type="organization",
            name=org.name,
            capabilities="[]",
        )
    )

    db.flush()

    repo = Repository(
        id=str(uuid4()),
        owner_id=org.id,
        name="audit-repo",
        slug="audit-repo",
        storage_key=str(uuid4()),
        default_branch="main",
        visibility="private",
    )

    db.add(repo)
    db.flush()

    actor = db.query(
        Actor
    ).filter(
        Actor.id == user.id
    ).first()

    assert actor is not None

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=user_actor.id,
        intent="Audit test change",
        status="proposed",
    )

    db.add(change)
    db.flush()

    db.add(
        ChangeEvent(
            change_id=change.id,
            actor_id=user_actor.id,
            event_type="change.created",
            to_status="proposed",
            metadata_json='{"source":"test"}',
            created_at=datetime.now(
                timezone.utc
            ),
        )
    )

    db.commit()

    app.dependency_overrides[
        get_current_user
    ] = lambda: user

    try:
        response = client.get(
            f"/v1/organizations/{org.id}/audit-logs"
        )
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload
    assert payload[0]["action"] == "change.created"
    assert payload[0]["resource_type"] == "change"
    assert payload[0][
        "resource_name"
    ].startswith("audit-repo:")
    assert payload[0][
        "metadata_json"
    ]["source"] == "test"


def test_audit_rejects_non_admin_member(
    client,
    db,
):
    owner = User(
        id=str(uuid4()),
        username="audit-admin",
        email="audit-admin@example.com",
        password_hash="test",
    )

    member = User(
        id=str(uuid4()),
        username="audit-member",
        email="audit-member@example.com",
        password_hash="test",
    )

    db.add_all(
        [
            owner,
            member,
        ]
    )
    db.flush()

    _create_human_actor(
        db,
        owner,
    )

    _create_human_actor(
        db,
        member,
    )

    org = Organization(
        id=str(uuid4()),
        name="audit-secure-org",
        display_name="Audit Secure Org",
    )

    db.add(org)
    db.flush()

    db.add_all(
        [
            OrganizationMember(
                organization_id=org.id,
                user_id=owner.id,
                role="owner",
            ),
            OrganizationMember(
                organization_id=org.id,
                user_id=member.id,
                role="member",
            ),
        ]
    )

    db.commit()

    app.dependency_overrides[
        get_current_user
    ] = lambda: member

    try:
        response = client.get(
            f"/v1/organizations/{org.id}/audit-logs"
        )
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

    assert response.status_code == 403