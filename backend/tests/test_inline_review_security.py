from uuid import uuid4

import pytest
from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.user import User
from app.services.inline_review_service import (
    InlineReviewService,
)
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


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


def setup_sec_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"sec_user_a_{uuid4().hex[:8]}",
        email=f"seca_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"sec_user_b_{uuid4().hex[:8]}",
        email=f"secb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    # Both users participate in authorization and inline-review flows.
    # User A is also the owner and PR author.
    _create_human_actor(
        db,
        user_a,
    )

    _create_human_actor(
        db,
        user_b,
    )

    repo_a = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"sec_repo_a_{uuid4().hex[:8]}",
        description="Sec Repo A",
        visibility="private",
    )

    repo_b = RepositoryService(db).create(
        owner_id=user_b.id,
        name=f"sec_repo_b_{uuid4().hex[:8]}",
        description="Sec Repo B",
        visibility="private",
    )

    agent_a = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="sec_agent_a",
        token_prefix="prefix_sec_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent_a)

    actor_a = Actor(
        id=agent_a.id,
        owner_id=user_a.id,
        type="agent",
        name=agent_a.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add(actor_a)

    agent_b = Agent(
        id=str(uuid4()),
        owner_id=user_b.id,
        name="sec_agent_b",
        token_prefix="prefix_sec_456",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent_b)

    actor_b = Actor(
        id=agent_b.id,
        owner_id=user_b.id,
        type="agent",
        name=agent_b.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add(actor_b)
    db.commit()

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor_a.id,
        intent="Sec Change A",
        risk_level="low",
        resulting_commit=(
            "1111111111111111111111111111111111111111"
        ),
        base_commit=(
            "0000000000000000000000000000000000000000"
        ),
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    change_b = Change(
        id=str(uuid4()),
        repository_id=repo_b.id,
        actor_id=actor_b.id,
        intent="Sec Change B",
        risk_level="low",
        resulting_commit=(
            "2222222222222222222222222222222222222222"
        ),
        base_commit=(
            "0000000000000000000000000000000000000000"
        ),
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    db.add_all(
        [
            change_a,
            change_b,
        ]
    )
    db.commit()

    svc = PullRequestService(db)

    pr_a = svc.create_pull_request(
        repo_a.id,
        user_a.id,
        change_a.id,
        "Sec PR A",
        "main",
    )

    pr_b = svc.create_pull_request(
        repo_b.id,
        user_b.id,
        change_b.id,
        "Sec PR B",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo_a,
        repo_b,
        pr_a,
        pr_b,
    )


def test_idor_and_bola_prevention(db, client):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        pr_a,
        pr_b,
    ) = setup_sec_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # Create comment on PR A as User A.
    svc = InlineReviewService(db)

    c_a = svc.create_comment(
        pull_request_id=pr_a.id,
        author_id=user_a.id,
        body="Secret comment on Private PR A",
    )

    db.commit()

    # User B tries to read PR A comments.
    app.dependency_overrides[
        get_current_user
    ] = lambda: user_b

    res_read = client.get(
        f"/v1/pull-requests/{pr_a.id}/comments"
    )

    assert (
        res_read.status_code
        == status.HTTP_404_NOT_FOUND
    )

    # User B tries to post a comment on PR A.
    res_post = client.post(
        f"/v1/pull-requests/{pr_a.id}/comments",
        json={
            "body": "Malicious comment"
        },
    )

    assert res_post.status_code in {
        status.HTTP_404_NOT_FOUND,
        status.HTTP_403_FORBIDDEN,
    }

    # User B tries to resolve User A's thread.
    res_res = client.post(
        f"/v1/pull-requests/{pr_a.id}/comments/{c_a.id}/resolve"
    )

    assert res_res.status_code in {
        status.HTTP_404_NOT_FOUND,
        status.HTTP_403_FORBIDDEN,
    }

    app.dependency_overrides.clear()


def test_path_traversal_and_input_injection_prevention(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        pr_a,
        pr_b,
    ) = setup_sec_fixtures(db)

    svc = InlineReviewService(db)

    # Path traversal attack.
    with pytest.raises(
        ValueError,
        match="Invalid file path",
    ):
        svc.create_comment(
            pull_request_id=pr_a.id,
            author_id=user_a.id,
            body="Attack body",
            path="../../../etc/passwd",
        )

    # Leading hyphen path attack.
    with pytest.raises(
        ValueError,
        match="Invalid file path",
    ):
        svc.create_comment(
            pull_request_id=pr_a.id,
            author_id=user_a.id,
            body="Attack body",
            path="-o/output.txt",
        )


def test_cross_pr_parent_id_injection_prevention(db):
    (
        user_a,
        user_b,
        repo_a,
        repo_b,
        pr_a,
        pr_b,
    ) = setup_sec_fixtures(db)

    svc = InlineReviewService(db)

    # Comment on PR A.
    c_a = svc.create_comment(
        pull_request_id=pr_a.id,
        author_id=user_a.id,
        body="Comment on PR A",
    )

    db.commit()

    # User B attempts to use a PR-A parent on PR B.
    with pytest.raises(
        ValueError,
        match="Parent comment belongs to a different PullRequest",
    ):
        svc.create_comment(
            pull_request_id=pr_b.id,
            author_id=user_b.id,
            body="Cross PR parent injection",
            parent_id=c_a.id,
        )