import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.ci_job import CIJob
from app.models.knowledge_node import KnowledgeNode
from app.models.knowledge_edge import KnowledgeEdge
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.change_service import ChangeService
from app.services.ci_service import CIService
from app.services.knowledge_graph_service import (
    index_repository_files,
    upsert_node,
    add_edge,
    search_nodes,
)
from app.services.pull_request_service import PullRequestService
from tests.conftest import ensure_test_actor


def test_sqlite_foreign_key_integrity(db):
    """
    Ensure SQLite foreign key enforcement is active.
    Attempting to insert a child row with non-existent parent must fail with FK violation.
    """
    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    actor = ensure_test_actor(db, user)

    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        name=f"repo_{uuid.uuid4().hex[:8]}",
        slug=f"repo_{uuid.uuid4().hex[:8]}",
        default_branch="main",
        storage_key=str(uuid.uuid4()),
    )
    db.add(repo)
    db.flush()

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Test FK integrity",
        base_commit="0" * 40,
        resulting_commit="1" * 40,
        status="proposed",
    )
    db.add(change)
    db.flush()

    cfile = ChangeFile(
        id=str(uuid.uuid4()),
        change_id=change.id,
        path="src/main.py",
        operation="modified",
        additions=10,
        deletions=2,
    )
    db.add(cfile)
    db.flush()

    pr = PullRequest(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Test PR",
        target_branch="main",
        status="open",
    )
    db.add(pr)
    db.flush()

    # Foreign key checks enabled
    if db.bind.dialect.name == "sqlite":
        res = db.execute(text("PRAGMA foreign_keys")).scalar()
        assert res == 1, "SQLite foreign keys must be ON"

    # Attempting to insert an orphaned change_file should fail
    orphaned_cf = ChangeFile(
        id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()), # non-existent change
        path="src/orphan.py",
        operation="added",
        additions=1,
        deletions=0,
    )
    db.add(orphaned_cf)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_pr_change_and_diff_statistics(db):
    """
    Ensure PR Change API exposes complete change information:
    - change id, status, commit info
    - files, additions, deletions, changed file count
    """
    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    actor = ensure_test_actor(db, user)

    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        name=f"repo_{uuid.uuid4().hex[:8]}",
        slug=f"repo_{uuid.uuid4().hex[:8]}",
        default_branch="main",
        storage_key=str(uuid.uuid4()),
    )
    db.add(repo)
    db.flush()

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Add math utilities",
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        status="recorded",
        risk_level="low",
    )
    db.add(change)
    db.flush()

    cf1 = ChangeFile(
        id=str(uuid.uuid4()),
        change_id=change.id,
        path="math/add.py",
        operation="added",
        additions=20,
        deletions=0,
    )
    cf2 = ChangeFile(
        id=str(uuid.uuid4()),
        change_id=change.id,
        path="math/subtract.py",
        operation="modified",
        additions=5,
        deletions=2,
    )
    db.add_all([cf1, cf2])
    db.flush()

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Add math utilities PR",
        target_branch="main",
    )
    db.commit()

    # Query PR Change directly
    result = pr_svc.get_pull_request_change(pr.id, user.id)
    assert result is not None
    pr_res, change_res = result
    assert change_res.id == change.id

    # Query ChangeFiles
    files = db.scalars(select(ChangeFile).where(ChangeFile.change_id == change.id)).all()
    assert len(files) == 2
    assert sum(f.additions for f in files) == 25
    assert sum(f.deletions for f in files) == 2


def test_automatic_ci_dispatch_on_pr_opened(db):
    """
    Ensure creating an open PR automatically queues a CIJob.
    """
    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    actor = ensure_test_actor(db, user)

    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        name=f"repo_{uuid.uuid4().hex[:8]}",
        slug=f"repo_{uuid.uuid4().hex[:8]}",
        default_branch="main",
        storage_key=str(uuid.uuid4()),
    )
    db.add(repo)
    db.flush()

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Automatic CI test change",
        base_commit="1" * 40,
        resulting_commit="2" * 40,
        status="recorded",
    )
    db.add(change)
    db.flush()

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="Automatic CI PR",
        target_branch="main",
    )
    db.commit()

    # Check CI job exists and is linked
    ci_jobs = db.scalars(select(CIJob).where(CIJob.pull_request_id == pr.id)).all()
    assert len(ci_jobs) == 1
    job = ci_jobs[0]
    assert job.commit_sha == change.resulting_commit
    assert job.repository_id == repo.id
    assert job.status in {CIJob.STATUS_QUEUED, CIJob.STATUS_RUNNING, CIJob.STATUS_PASSED}


def test_agent_pr_review_requested_lineage(db):
    """
    Ensure Agent-created PR creates a pending ChangeReview and pull_request.review_requested event.
    """
    owner = User(
        id=str(uuid.uuid4()),
        username=f"owner_{uuid.uuid4().hex[:8]}",
        email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(owner)
    db.flush()
    owner_actor = ensure_test_actor(db, owner)

    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=owner.id,
        name=f"agent_repo_{uuid.uuid4().hex[:8]}",
        slug=f"agent_repo_{uuid.uuid4().hex[:8]}",
        default_branch="main",
        storage_key=str(uuid.uuid4()),
    )
    db.add(repo)
    db.flush()

    agent_id = str(uuid.uuid4())
    agent_actor = Actor(
        id=agent_id,
        owner_id=owner.id,
        type="agent",
        name=f"agent_{uuid.uuid4().hex[:8]}",
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    agent = Agent(
        id=agent_id,
        owner_id=owner.id,
        name=agent_actor.name,
        token_prefix="agent_pref_",
        token_hash="hash",
        status="active",
        is_active=True,
    )
    db.add_all([agent_actor, agent])
    db.flush()

    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions='["repository.read", "repository.write", "change.create"]',
        enabled=True,
    )
    db.add(access)
    db.flush()

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Agent Feature",
        base_commit="3" * 40,
        resulting_commit="4" * 40,
        status="recorded",
    )
    db.add(change)
    db.flush()

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=agent_actor.id,
        source_change_id=change.id,
        title="Agent PR with Review Request",
        target_branch="main",
    )
    db.commit()

    # Review must exist with pending status
    reviews = db.scalars(select(ChangeReview).where(ChangeReview.change_id == change.id)).all()
    assert len(reviews) == 1
    assert reviews[0].status == "pending"
    assert reviews[0].requested_by == owner.id

    # CI job must also be created for the agent PR
    ci_jobs = db.scalars(select(CIJob).where(CIJob.pull_request_id == pr.id)).all()
    assert len(ci_jobs) == 1
    assert ci_jobs[0].commit_sha == change.resulting_commit


def test_knowledge_graph_node_indexing_service(db):
    """
    Ensure knowledge graph indexing service creates KnowledgeNode and KnowledgeEdge records.
    """
    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    actor = ensure_test_actor(db, user)

    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        name=f"kg_repo_{uuid.uuid4().hex[:8]}",
        slug=f"kg_repo_{uuid.uuid4().hex[:8]}",
        default_branch="main",
        storage_key=str(uuid.uuid4()),
    )
    db.add(repo)
    db.flush()

    node_file = upsert_node(
        db=db,
        repository_id=repo.id,
        entity_type="file",
        name="src/calculator.py",
        summary="Calculator module",
    )
    node_func = upsert_node(
        db=db,
        repository_id=repo.id,
        entity_type="function",
        name="src/calculator.py:power",
        summary="Calculates base ** exp",
    )
    edge = add_edge(
        db=db,
        source_node_id=node_file.id,
        target_node_id=node_func.id,
        relationship_type="defines",
    )
    db.commit()

    # Search
    results = search_nodes(db, repository_id=repo.id, query="power")
    assert len(results) >= 1
    assert any(n.name == "src/calculator.py:power" for n in results)


def test_ci_failure_and_execution_status_propagation(db):
    """
    Ensure CI execution failures are correctly persisted and exposed with failure reasons.
    """
    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    actor = ensure_test_actor(db, user)

    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        name=f"ci_repo_{uuid.uuid4().hex[:8]}",
        slug=f"ci_repo_{uuid.uuid4().hex[:8]}",
        default_branch="main",
        storage_key=str(uuid.uuid4()),
    )
    db.add(repo)
    db.flush()

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="CI Failure test",
        base_commit="1" * 40,
        resulting_commit="2" * 40,
        status="recorded",
    )
    db.add(change)
    db.flush()

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=user.id,
        source_change_id=change.id,
        title="CI Failure PR",
        target_branch="main",
    )
    db.commit()

    ci_svc = CIService(db)
    jobs = ci_svc.list_jobs_for_pr(pr.id, user.id)
    assert len(jobs) >= 1
    job = jobs[0]

    # Mark failed
    job.status = CIJob.STATUS_FAILED
    job.exit_code = 1
    job.failure_reason = "Tests failed: 2 assertion errors"
    db.commit()

    updated_job = ci_svc.get_job(job.id, user.id)
    assert updated_job.status == "failed"
    assert updated_job.exit_code == 1
    assert "assertion errors" in updated_job.failure_reason


def test_changes_api_created_at_and_updated_at(db):
    """
    Ensure Change API schemas include created_at and updated_at.
    """
    from app.api.changes import _to_change_response
    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    actor = ensure_test_actor(db, user)

    now = datetime.now(timezone.utc)
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=str(uuid.uuid4()),
        actor_id=actor.id,
        intent="Test Change Timestamps",
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        status="recorded",
        created_at=now,
        updated_at=now,
    )
    resp = _to_change_response(change, actor, db)
    assert resp.created_at == now
    assert resp.updated_at == now

