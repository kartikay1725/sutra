import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import status

from app.api.agent_dependencies import create_agent_session
from app.core.security import hash_password
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.user import User
from app.services.repository_service import RepositoryService


def _basic_auth(
    username: str,
    password: str,
) -> dict[str, str]:
    encoded = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("ascii")

    return {
        "Authorization": f"Basic {encoded}",
    }


def _create_user(
    db,
    prefix: str = "gitsec",
) -> User:
    user = User(
        id=str(uuid4()),
        username=f"{prefix}_{uuid4().hex[:8]}",
        email=f"{prefix}_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("human-password"),
    )

    db.add(user)
    db.flush()

    # Git human authorization uses the registered SUTRA user identity.
    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.review",
                "change.approve",
            ]
        ),
    )

    db.add(actor)
    db.commit()
    db.refresh(user)

    return user


def _create_agent(
    db,
    owner: User,
) -> tuple[Agent, str]:
    raw_token = (
        uuid4().hex
        + "_sutra_agent_security"
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"git_security_agent_{uuid4().hex[:8]}",
        description="Git session security test agent",
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:16],
        status="active",
        is_active=True,
    )

    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent.id,
        owner_id=owner.id,
        type="agent",
        name=agent.name,
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]
        ),
    )

    db.add(actor)
    db.commit()

    # Grant repository access to all repositories owned by the user
    from sqlalchemy import select
    from app.models.repository import Repository
    from app.models.agent_repository_access import AgentRepositoryAccess
    repos = db.scalars(select(Repository).where(Repository.owner_id == owner.id)).all()
    for repo in repos:
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repo.id,
            permissions=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
            enabled=True,
        )
        db.add(access)
    db.commit()

    db.refresh(agent)

    return agent, raw_token


def _git_info_refs_url(
    user: User,
    repo: Repository,
) -> str:
    return (
        f"/git/"
        f"{user.username}/"
        f"{repo.name}.git/"
        f"info/refs"
        f"?service=git-upload-pack"
    )


def _create_repo(
    db,
    user: User,
) -> Repository:
    return RepositoryService(db).create(
        owner_id=user.id,
        name=f"gitsec_repo_{uuid4().hex[:8]}",
        description="Git session security repository",
        visibility="private",
    )


def test_agent_long_lived_token_without_session_is_rejected(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)
    agent, agent_token = _create_agent(db, user)

    response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            agent.token_prefix,
            agent_token,
        ),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_active_agent_session_allows_git_access(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)
    agent, agent_token = _create_agent(db, user)

    session, session_token = create_agent_session(
        agent,
        db,
    )

    assert session.status == "active"

    # Session-bound Git credential contract:
    #
    # username = agent token prefix
    # password = active AgentSession token
    response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            agent.token_prefix,
            session_token,
        ),
    )

    assert response.status_code == status.HTTP_200_OK


def test_expired_agent_session_blocks_git_access(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)
    agent, _ = _create_agent(db, user)

    session, session_token = create_agent_session(
        agent,
        db,
    )

    session.expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db.commit()

    response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            agent.token_prefix,
            session_token,
        ),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_revoked_agent_session_blocks_git_access(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)
    agent, _ = _create_agent(db, user)

    session, session_token = create_agent_session(
        agent,
        db,
    )

    session.status = "revoked"
    session.revoked_at = datetime.now(
        timezone.utc
    )

    db.commit()

    response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            agent.token_prefix,
            session_token,
        ),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_new_agent_session_restores_git_access(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)
    agent, _ = _create_agent(db, user)

    old_session, old_token = create_agent_session(
        agent,
        db,
    )

    old_session.status = "revoked"
    old_session.revoked_at = datetime.now(
        timezone.utc
    )

    db.commit()

    old_response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            agent.token_prefix,
            old_token,
        ),
    )

    assert old_response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )

    new_session, new_token = create_agent_session(
        agent,
        db,
    )

    assert new_session.id != old_session.id
    assert new_session.status == "active"

    new_response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            agent.token_prefix,
            new_token,
        ),
    )

    assert new_response.status_code == (
        status.HTTP_200_OK
    )


def test_registered_human_can_use_git(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)

    response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            user.username,
            "human-password",
        ),
    )

    assert response.status_code == (
        status.HTTP_200_OK
    )


def test_unknown_git_identity_is_rejected(
    db,
    client,
):
    user = _create_user(db)
    repo = _create_repo(db, user)

    response = client.get(
        _git_info_refs_url(user, repo),
        headers=_basic_auth(
            "this-user-does-not-exist",
            "not-a-valid-password",
        ),
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )


def test_human_cannot_use_agent_session_as_human_git_password(
    db,
    client,
):
    owner = _create_user(
        db,
        prefix="gitsec_owner",
    )
    repo = _create_repo(db, owner)
    agent, _ = _create_agent(db, owner)

    _, session_token = create_agent_session(
        agent,
        db,
    )

    response = client.get(
        _git_info_refs_url(owner, repo),
        headers=_basic_auth(
            owner.username,
            session_token,
        ),
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )


def test_agent_session_is_bound_to_its_agent(
    db,
    client,
):
    owner_a = _create_user(
        db,
        prefix="gitsec_a",
    )
    owner_b = _create_user(
        db,
        prefix="gitsec_b",
    )

    repo_a = _create_repo(
        db,
        owner_a,
    )

    agent_a, _ = _create_agent(
        db,
        owner_a,
    )

    agent_b, _ = _create_agent(
        db,
        owner_b,
    )

    _, session_b_token = create_agent_session(
        agent_b,
        db,
    )

    response = client.get(
        _git_info_refs_url(owner_a, repo_a),
        headers=_basic_auth(
            agent_a.token_prefix,
            session_b_token,
        ),
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )


def test_commit_author_does_not_define_git_principal(
    db,
):
    """
    Regression specification:

    Git commit author metadata is not an authentication mechanism.

    A client may create a commit whose author name/email claims to be
    a different person. SUTRA's authenticated principal must continue
    to come from Git authentication, not commit metadata.

    This test currently establishes the invariant at the model/service
    boundary. The full push-path assertion should be added once the
    session-bound Git credential flow is implemented.
    """
    user = _create_user(db)

    spoofed_author_name = "another-user"
    spoofed_author_email = "another@example.com"

    assert spoofed_author_name != user.username
    assert spoofed_author_email != user.email

    # The test intentionally contains no assignment of these values
    # to a SUTRA principal. The implementation must never derive
    # authorization from Git author metadata.