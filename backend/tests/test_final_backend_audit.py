from uuid import uuid4

from app.core.security import hash_password
from app.models.actor import Actor
from app.models.repository import Repository
from app.models.user import User


def make_user(db, prefix="audit-user"):
    suffix = uuid4().hex[:10]
    user_id = str(uuid4())
    username = f"{prefix}-{suffix}"
    email = f"{username}@example.com"

    user = User(
        id=user_id,
        username=username,
        email=email,
        password_hash=hash_password("password"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Some production/test paths create the human Actor automatically,
    # while other isolated test setups don't. For this audit we need a
    # deterministic User -> Actor relationship, so create it only when
    # the fixture has not already provisioned one.
    actor = db.get(Actor, user.id)

    if actor is None:
        actor = Actor(
            id=user.id,
            owner_id=user.id,
            type="human",
            name=user.username,
            capabilities=(
                '["repository.read",'
                '"repository.write",'
                '"change.create"]'
            ),
        )
        db.add(actor)
        db.commit()
        db.refresh(actor)

    assert actor.owner_id == user.id
    assert actor.type == "human"
    assert actor.name == user.username

    return user, actor

def make_repo(
    db,
    owner_id: str,
    visibility: str = "public",
    prefix="audit-repo",
):
    suffix = uuid4().hex[:10]
    name = f"{prefix}-{suffix}"

    repo = Repository(
        owner_id=owner_id,
        name=name,
        slug=name,
        description="Final backend audit repository",
        storage_key=f"audit-{uuid4().hex}",
        visibility=visibility,
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    return repo


def login(client, user):
    response = client.post(
        "/v1/auth/login",
        json={
            "login": user.email,
            "password": "password",
        },
    )

    assert response.status_code == 200, response.text

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


def test_public_profile_is_anonymous_and_hides_private_repositories(
    client,
    db,
):
    user, actor = make_user(db)

    public_repo = make_repo(
        db,
        user.id,
        visibility="public",
    )

    private_repo = make_repo(
        db,
        user.id,
        visibility="private",
    )

    response = client.get(
        f"/v1/profiles/{user.username}"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["username"] == user.username
    assert data["public_repository_count"] == 1

    repository_ids = {
        repo["id"]
        for repo in data["repositories"]
    }

    assert public_repo.id in repository_ids
    assert private_repo.id not in repository_ids


def test_profile_update_persists_public_identity_and_social_links(
    client,
    db,
):
    user, actor = make_user(db)

    headers = login(client, user)

    payload = {
        "full_name": "Final Audit Developer",
        "bio": "Building software with SUTRA.",
        "social_links": {
            "github": "https://github.com/example",
            "linkedin": "https://linkedin.com/in/example",
            "x": "https://x.com/example",
            "instagram": "https://instagram.com/example",
            "reddit": "https://reddit.com/u/example",
            "youtube": "https://youtube.com/@example",
            "website": "https://example.com",
        },
    }

    response = client.patch(
        "/v1/auth/me",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200, response.text

    saved = response.json()

    assert saved["full_name"] == payload["full_name"]
    assert saved["bio"] == payload["bio"]
    assert saved["social_links"] == payload["social_links"]

    public_response = client.get(
        f"/v1/profiles/{user.username}"
    )

    assert public_response.status_code == 200, public_response.text

    public_profile = public_response.json()

    assert public_profile["full_name"] == payload["full_name"]
    assert public_profile["bio"] == payload["bio"]
    assert (
        public_profile["social_links"]
        == payload["social_links"]
    )


def test_profile_update_rejects_duplicate_email(
    client,
    db,
):
    user_a, _ = make_user(
        db,
        prefix="audit-email-a",
    )
    user_b, _ = make_user(
        db,
        prefix="audit-email-b",
    )

    headers = login(client, user_a)

    response = client.patch(
        "/v1/auth/me",
        json={
            "email": user_b.email,
        },
        headers=headers,
    )

    assert response.status_code == 409


def test_follow_unfollow_lifecycle(
    client,
    db,
):
    follower, _ = make_user(
        db,
        prefix="audit-follower",
    )
    target, _ = make_user(
        db,
        prefix="audit-target",
    )

    headers = login(
        client,
        follower,
    )

    profile_before = client.get(
        f"/v1/profiles/{target.username}"
    )

    assert profile_before.status_code == 200
    assert profile_before.json()["followers"] == 0

    follow = client.post(
        f"/v1/users/{target.username}/follow",
        headers=headers,
    )

    assert follow.status_code == 204

    profile_after_follow = client.get(
        f"/v1/profiles/{target.username}"
    )

    assert profile_after_follow.status_code == 200
    assert (
        profile_after_follow.json()["followers"]
        == 1
    )

    # Repeating the same follow must not create a duplicate relationship.
    duplicate_follow = client.post(
        f"/v1/users/{target.username}/follow",
        headers=headers,
    )

    assert duplicate_follow.status_code == 204

    profile_after_duplicate = client.get(
        f"/v1/profiles/{target.username}"
    )

    assert (
        profile_after_duplicate.json()["followers"]
        == 1
    )

    unfollow = client.delete(
        f"/v1/users/{target.username}/follow",
        headers=headers,
    )

    assert unfollow.status_code == 204

    profile_after_unfollow = client.get(
        f"/v1/profiles/{target.username}"
    )

    assert (
        profile_after_unfollow.json()["followers"]
        == 0
    )


def test_self_follow_is_rejected(
    client,
    db,
):
    user, _ = make_user(
        db,
        prefix="audit-self-follow",
    )

    headers = login(client, user)

    response = client.post(
        f"/v1/users/{user.username}/follow",
        headers=headers,
    )

    assert response.status_code == 400


def test_follow_requires_authentication(
    client,
    db,
):
    user, _ = make_user(
        db,
        prefix="audit-auth-follow",
    )

    response = client.post(
        f"/v1/users/{user.username}/follow"
    )

    assert response.status_code == 401


def test_public_profile_not_found(
    client,
):
    response = client.get(
        f"/v1/profiles/nonexistent-{uuid4().hex}"
    )

    assert response.status_code == 404


def test_profile_schema_contains_new_fields():
    from app.models.user import User

    columns = set(
        User.__table__.columns.keys()
    )

    assert "full_name" in columns
    assert "bio" in columns
    assert "social_links" in columns


def test_profile_public_response_never_exposes_credentials(
    client,
    db,
):
    user, _ = make_user(
        db,
        prefix="audit-public-safety",
    )

    response = client.get(
        f"/v1/profiles/{user.username}"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "password_hash" not in data
    assert "email" not in data
    assert "password" not in data
    assert "access_token" not in data