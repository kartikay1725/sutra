from uuid import uuid4

from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.user import User
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


def setup_api_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"api_user_a_{uuid4().hex[:8]}",
        email=f"apia_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"api_user_b_{uuid4().hex[:8]}",
        email=f"apib_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    # Both users participate in the API authorization flow.
    # User A is also the PullRequest author.
    _create_human_actor(
        db,
        user_a,
    )

    _create_human_actor(
        db,
        user_b,
    )

    repo = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"api_repo_{uuid4().hex[:8]}",
        description="API Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="api_agent",
        token_prefix="prefix_api_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_a.id,
        type="agent",
        name=agent.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="API Change",
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

    db.add(change)
    db.commit()

    svc = PullRequestService(db)

    pr = svc.create_pull_request(
        repo.id,
        user_a.id,
        change.id,
        "API PR",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo,
        change,
        pr,
    )


def test_inline_comments_api_endpoints(db, client):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[
        get_current_user
    ] = lambda: user_a

    # 1. Get PR files & diff.
    res_files = client.get(
        f"/v1/pull-requests/{pr.id}/files"
    )

    assert (
        res_files.status_code
        == status.HTTP_200_OK
    )

    res_diff = client.get(
        f"/v1/pull-requests/{pr.id}/diff"
    )

    assert (
        res_diff.status_code
        == status.HTTP_200_OK
    )

    # 2. Post general comment.
    payload_gen = {
        "body": "Great PR!"
    }

    res_gen = client.post(
        f"/v1/pull-requests/{pr.id}/comments",
        json=payload_gen,
    )

    assert (
        res_gen.status_code
        == status.HTTP_201_CREATED
    )

    gen_data = res_gen.json()

    assert gen_data["body"] == "Great PR!"
    assert gen_data["path"] is None

    # 3. Post inline comment.
    payload_inline = {
        "body": "Fix variable name",
        "path": "src/app.py",
        "diff_side": "RIGHT",
        "line_number": 12,
    }

    res_inline = client.post(
        f"/v1/pull-requests/{pr.id}/comments",
        json=payload_inline,
    )

    assert (
        res_inline.status_code
        == status.HTTP_201_CREATED
    )

    inline_data = res_inline.json()

    assert inline_data["path"] == "src/app.py"
    assert inline_data["line_number"] == 12

    comment_id = inline_data["id"]

    # 4. Post reply via reply endpoint.
    payload_reply = {
        "body": "Will fix in next commit"
    }

    res_reply = client.post(
        f"/v1/pull-requests/{pr.id}/comments/{comment_id}/reply",
        json=payload_reply,
    )

    assert (
        res_reply.status_code
        == status.HTTP_201_CREATED
    )

    reply_data = res_reply.json()

    assert reply_data["parent_id"] == comment_id

    # 5. List comments.
    res_list = client.get(
        f"/v1/pull-requests/{pr.id}/comments"
    )

    assert (
        res_list.status_code
        == status.HTTP_200_OK
    )

    assert len(
        res_list.json()
    ) == 3

    # 6. Resolve thread.
    res_res = client.post(
        f"/v1/pull-requests/{pr.id}/comments/{comment_id}/resolve"
    )

    assert (
        res_res.status_code
        == status.HTTP_200_OK
    )

    assert (
        res_res.json()["status"]
        == "resolved"
    )

    # 7. Reopen thread.
    res_reopen = client.post(
        f"/v1/pull-requests/{pr.id}/comments/{comment_id}/reopen"
    )

    assert (
        res_reopen.status_code
        == status.HTTP_200_OK
    )

    assert (
        res_reopen.json()["status"]
        == "active"
    )

    # 8. Unauthorized user (User B) attempts
    # to view private PR comments.
    app.dependency_overrides[
        get_current_user
    ] = lambda: user_b

    res_unauth = client.get(
        f"/v1/pull-requests/{pr.id}/comments"
    )

    assert (
        res_unauth.status_code
        == status.HTTP_404_NOT_FOUND
    )

    app.dependency_overrides.clear()