from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.actor import Actor
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User


def create_pr_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"pr_user_{uuid4().hex[:8]}",
        email=f"pr_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    user_actor = Actor(
        id=user.id,
        type="human",
        name=user.username,
        owner_id=user.id,
    )
    db.add(user_actor)
    db.flush()

    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name=f"pr_repo_{uuid4().hex[:8]}",
        slug=f"pr_repo_{uuid4().hex[:8]}",
        visibility="private",
        storage_key=str(uuid4()),
    )
    db.add(repo)

    actor = Actor(
        id=str(uuid4()),
        owner_id=user.id,
        type="agent",
        name="pr_actor",
    )
    db.add(actor)
    db.flush()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test Change",
        operation_key=uuid4().hex * 2,
    )
    db.add(change)
    db.commit()

    return user, repo, change


def test_pull_request_valid_statuses(db):
    user, repo, change = create_pr_fixtures(db)

    valid_statuses = ["draft", "open", "approved", "merged", "closed", "rejected"]
    for i, status in enumerate(valid_statuses):
        c = Change(
            id=str(uuid4()),
            repository_id=repo.id,
            actor_id=change.actor_id,
            intent=f"Change {i}",
            operation_key=(uuid4().hex * 2)[:64],
        )
        db.add(c)
        db.commit()

        pr = PullRequest(
            repository_id=repo.id,
            author_id=user.id,
            source_change_id=c.id,
            title=f"PR {status}",
            target_branch="main",
            status=status,
        )
        db.add(pr)
        db.commit()
        assert pr.id is not None
        assert pr.status == status


def test_pull_request_invalid_status_rejection(db):
    user, repo, change = create_pr_fixtures(db)

    pr = PullRequest(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Invalid PR",
        target_branch="main",
        status="invalid_status",
    )
    db.add(pr)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_pull_request_unique_source_change_id(db):
    user, repo, change = create_pr_fixtures(db)

    pr1 = PullRequest(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="PR 1",
        target_branch="main",
    )
    db.add(pr1)
    db.commit()

    pr2 = PullRequest(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="PR 2",
        target_branch="main",
    )
    db.add(pr2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_pull_request_foreign_key_constraints(db):
    if db.bind.dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON;"))

    user, repo, change = create_pr_fixtures(db)

    # Invalid repository_id
    pr_bad_repo = PullRequest(
        repository_id=str(uuid4()),
        author_id=user.id,
        source_change_id=change.id,
        title="Bad Repo PR",
        target_branch="main",
    )
    db.add(pr_bad_repo)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Invalid author_id
    pr_bad_author = PullRequest(
        repository_id=repo.id,
        author_id=str(uuid4()),
        source_change_id=change.id,
        title="Bad Author PR",
        target_branch="main",
    )
    db.add(pr_bad_author)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
