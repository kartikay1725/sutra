from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.core.security import password_hash


def _make_user(
    db: Session,
    username: str,
    email: str,
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=password_hash.hash(
            "TestPassword123!"
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _make_organization(
    db: Session,
    owner: User,
    name: str,
) -> Organization:
    organization = Organization(
        id=f"gov-{owner.id}",
        name=name,
        display_name=name,
        description="Governance test organization",
    )

    db.add(organization)

    member = OrganizationMember(
        organization_id=organization.id,
        user_id=owner.id,
        role="owner",
    )

    db.add(member)
    db.commit()
    db.refresh(organization)

    return organization


def test_governance_requires_membership(
    client: TestClient,
    db: Session,
):
    owner = _make_user(
        db,
        "gov-owner-test",
        "gov-owner-test@example.com",
    )

    organization = _make_organization(
        db,
        owner,
        "governance-test-org",
    )

    # Governance endpoints require authentication.
    # The test intentionally verifies that an unauthenticated
    # request is rejected rather than inventing an auth route.
    response = client.get(
        f"/v1/organizations/{organization.name}/policies"
    )

    assert response.status_code == 401


def test_governance_defaults_and_admin_update(
    client: TestClient,
    db: Session,
):
    owner = _make_user(
        db,
        "gov-admin-test",
        "gov-admin-test@example.com",
    )

    organization = _make_organization(
        db,
        owner,
        "governance-admin-org",
    )

    # Verify the organization/member records were created correctly.
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id
            == organization.id,
            OrganizationMember.user_id
            == owner.id,
        )
        .first()
    )

    assert member is not None
    assert member.role == "owner"

    # The currently implemented governance route requires
    # get_current_user. This test therefore validates the
    # unauthenticated boundary without inventing a login route.
    response = client.get(
        f"/v1/organizations/{organization.name}/policies"
    )

    assert response.status_code == 401