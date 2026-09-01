from datetime import datetime, timezone, timedelta
import uuid

import pytest
from app.models import GitPushEvent
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.actor import Actor
from app.models.repository import Repository
from app.models.user import User
from app.services.git_push_event_service import (
    GitPushEventService,
)
from app.services.git_push_event_worker import (
    GitPushEventWorker,
)
from app.services.change_service import ChangeService
from app.services.change_policy_service import (
    PolicyDecision,
    ChangePolicyService,
)


@pytest.fixture(autouse=True)
def mock_git_and_policy(monkeypatch):
    # Mock Git operations on ChangeService
    monkeypatch.setattr(
        ChangeService,
        "resolve_commit",
        lambda self, repo, commit: commit,
    )
    monkeypatch.setattr(
        ChangeService,
        "_classify_ref_update",
        lambda self, repo, b, res: "update",
    )
    monkeypatch.setattr(
        ChangeService,
        "get_changed_files",
        lambda self, repo, b, res: [],
    )

    # Mock ChangePolicyService evaluate
    monkeypatch.setattr(
        ChangePolicyService,
        "evaluate",
        lambda self, change: PolicyDecision(
            decision=ChangePolicyService.ALLOW,
            reason="Allowed",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        ),
    )

@pytest.fixture()
def db_factory(tmp_path):
    database_path = tmp_path / "worker_test.db"

    engine = create_engine(
        f"sqlite:///{database_path}",
        pool_pre_ping=True,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    try:
        yield SessionLocal
    finally:
        engine.dispose()
@pytest.fixture()
def db(db_factory):
    session = db_factory()

    try:
        yield session
    finally:
        session.close()

def make_user(db: Session) -> User:
    username = f"user-{uuid.uuid4().hex[:8]}"

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
    )

    db.add(user)
    db.flush()

    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, user)

    return user


def make_repository(
    db: Session,
    owner_id: str,
) -> Repository:
    repository_id = f"repo-{uuid.uuid4().hex[:8]}"

    repository = Repository(
        id=repository_id,
        owner_id=owner_id,
        name=repository_id,
        slug=repository_id.lower(),
        description="Worker test repository",
        visibility="private",
        default_branch="main",
        storage_key=f"{repository_id}.git",
    )

    db.add(repository)
    db.flush()

    return repository


from app.models.agent import Agent


def make_actor(
    db: Session,
    owner_id: str,
) -> Actor:
    agent_id = str(uuid.uuid4())

    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name=f"agent-{uuid.uuid4().hex[:8]}",
        description="Test agent",
        provider="test",
        model="test",
        token_hash="unused",
        token_prefix=f"sa_{uuid.uuid4().hex[:8]}",
        status="active",
        is_active=True,
    )

    actor = Actor(
        id=agent_id,
        type="agent",
        name=agent.name,
        owner_id=owner_id,
        capabilities=(
            '["repository.read",'
            '"repository.write",'
            '"change.create"]'
        ),
    )

    db.add(agent)
    db.add(actor)
    db.flush()

    return actor



def create_event(
    db: Session,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
    )

    actor = make_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)

    event = service.create_event(
        repository=repository,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    return event


def test_worker_validates_configuration():
    with pytest.raises(
        ValueError,
        match="interval_seconds cannot be negative",
    ):
        GitPushEventWorker(
            interval_seconds=-1,
        )

    with pytest.raises(
        ValueError,
        match="batch_size must be positive",
    ):
        GitPushEventWorker(
            batch_size=0,
        )

    with pytest.raises(
        ValueError,
        match="batch_size cannot exceed 1000",
    ):
        GitPushEventWorker(
            batch_size=1001,
        )

    with pytest.raises(
        ValueError,
        match="stale_timeout_seconds must be positive",
    ):
        GitPushEventWorker(
            stale_timeout_seconds=0,
        )


def test_worker_empty_cycle(db: Session, monkeypatch):
    monkeypatch.setattr(
        "app.services.git_push_event_worker.SessionLocal",
        lambda: db,
    )

    worker = GitPushEventWorker(
        interval_seconds=0,
        batch_size=10,
        stale_timeout_seconds=300,
    )

    assert worker.run_once() == 0


def test_worker_claims_and_processes_event(
    db: Session,
    db_factory,
    monkeypatch,
):
    event = create_event(db)

    monkeypatch.setattr(
        "app.services.git_push_event_worker.SessionLocal",
        db_factory,
    )

    worker = GitPushEventWorker(
        interval_seconds=0,
        batch_size=10,
        stale_timeout_seconds=300,
    )

    claimed = worker.run_once()

    assert claimed == 1

    db.expire_all()
    refreshed = (
        db.query(GitPushEvent)
        .filter(GitPushEvent.id == event.id)
        .one()
    )

    print("LAST ERROR:", refreshed.last_error)
    assert (
        refreshed.status
        == GitPushEventService.STATUS_PROCESSED
    )

    assert refreshed.processed_at is not None
    assert refreshed.last_error is None


def test_worker_recovers_stale_event(
    db: Session,
    db_factory,
    monkeypatch,
):
    event = create_event(db)

    service = GitPushEventService(db)

    claimed = service.claim_pending(
        limit=10,
    )

    assert len(claimed) == 1

    event = claimed[0]

    event.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=600)
    )
    event.updated_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=600)
    )

    db.commit()

    # recover_stale_processing will be called inside run_once.
    # We want the event to be claimed immediately after recovery.
    # Since recovery sets next_attempt_at to the future, we need to mock datetime or run run_once, then update next_attempt_at, and run_once again.
    # Let's just run_once to recover it.
    
    monkeypatch.setattr(
        "app.services.git_push_event_worker.SessionLocal",
        db_factory,
    )

    worker = GitPushEventWorker(
        interval_seconds=0,
        batch_size=10,
        stale_timeout_seconds=300,
    )

    # First cycle recovers it and sets it to failed with future next_attempt_at
    worker.run_once()
    
    db.expire_all()
    refreshed = db.query(GitPushEvent).filter(GitPushEvent.id == event.id).one()
    
    assert refreshed.status == GitPushEventService.STATUS_FAILED
    
    # Artificially expire the backoff
    refreshed.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    
    # Second cycle processes it
    worker.run_once()

    db.expire_all()
    refreshed = (
        db.query(GitPushEvent)
        .filter(GitPushEvent.id == event.id)
        .one()
    )

    assert (
        refreshed.status
        == GitPushEventService.STATUS_PROCESSED
    )

    assert event.attempts == 2


def test_worker_stop_signal():
    worker = GitPushEventWorker(
        interval_seconds=0,
    )

    assert worker.stopped is False

    worker.stop()

    assert worker.stopped is True


def test_worker_survives_unexpected_cycle_failure(
    monkeypatch,
):
    class BrokenSession:
        def rollback(self):
            pass

        def close(self):
            pass

    def broken_session():
        raise RuntimeError(
            "database unavailable"
        )

    monkeypatch.setattr(
        "app.services.git_push_event_worker.SessionLocal",
        broken_session,
    )

    worker = GitPushEventWorker(
        interval_seconds=0,
    )

    assert worker.run_once() == 0


def test_worker_lease_is_assigned(
    db: Session,
):
    event = create_event(db)

    service = GitPushEventService(db)

    claimed = service.claim_pending(
        limit=10,
        worker_id="worker-a",
        lease_seconds=300,
    )

    assert len(claimed) == 1

    refreshed = (
        db.query(GitPushEvent)
        .filter(
            GitPushEvent.id == event.id
        )
        .one()
    )

    assert refreshed.status == "processing"
    assert refreshed.worker_id == "worker-a"
    assert refreshed.lease_expires_at is not None


def test_worker_cannot_renew_another_workers_lease(
    db: Session,
):
    event = create_event(db)

    service = GitPushEventService(db)

    claimed = service.claim_pending(
        limit=10,
        worker_id="worker-a",
        lease_seconds=300,
    )

    with pytest.raises(
        ValueError,
        match="Worker does not own event lease",
    ):
        service.renew_lease(
            claimed[0],
            worker_id="worker-b",
        )


def test_worker_can_renew_own_lease(
    db: Session,
):
    event = create_event(db)

    service = GitPushEventService(db)

    claimed = service.claim_pending(
        limit=10,
        worker_id="worker-a",
        lease_seconds=300,
    )

    before = claimed[0].lease_expires_at

    service.renew_lease(
        claimed[0],
        worker_id="worker-a",
        lease_seconds=600,
    )

    assert (
        claimed[0].lease_expires_at
        > before
    )


def test_valid_lease_is_not_recovered(
    db: Session,
):
    event = create_event(db)

    service = GitPushEventService(db)

    service.claim_pending(
        limit=10,
        worker_id="worker-a",
        lease_seconds=300,
    )

    recovered = (
        service.recover_stale_processing(
            timeout_seconds=1
        )
    )

    assert recovered == 0

    db.refresh(event)

    assert event.status == "processing"
    assert event.worker_id == "worker-a"


def test_expired_lease_is_recovered(
    db: Session,
):
    event = create_event(db)

    service = GitPushEventService(db)

    claimed = service.claim_pending(
        limit=10,
        worker_id="worker-a",
        lease_seconds=1,
    )

    from datetime import timedelta

    claimed[0].lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=10)
    )

    claimed[0].updated_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=10)
    )

    db.commit()

    recovered = (
        service.recover_stale_processing(
            timeout_seconds=1
        )
    )

    assert recovered == 1

    db.refresh(event)

    assert event.status == "failed"
    assert event.worker_id is None
    assert event.lease_expires_at is None
from app.services.git_push_event_processor import PermanentError

def test_retryable_failure_backoff(db: Session, monkeypatch):
    event = create_event(db)
    
    # Mock processor to raise Exception (retryable)
    def failing_processor(*args, **kwargs):
        raise Exception("Temporary failure")
        
    monkeypatch.setattr(
        "app.services.git_push_event_processor.GitPushEventProcessor.process_claimed_event",
        failing_processor
    )
    
    service = GitPushEventService(db)
    event = service.claim_pending(limit=1, worker_id="worker-a")[0]
    
    service.mark_failed(event, "Temporary failure", permanent=False)
    
    db.refresh(event)
    assert event.status == "failed"
    assert event.attempts == 1
    assert event.next_attempt_at is not None
    assert event.next_attempt_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)

def test_permanent_failure_dead_letter(db: Session, monkeypatch):
    event = create_event(db)
    
    service = GitPushEventService(db)
    event = service.claim_pending(limit=1, worker_id="worker-a")[0]
    
    service.mark_failed(event, "Agent actor no longer exists", permanent=True)
    
    db.refresh(event)
    assert event.status == "dead_letter"
    assert event.next_attempt_at is None

def test_max_attempts_dead_letter(db: Session, monkeypatch):
    event = create_event(db)
    
    service = GitPushEventService(db)
    event = service.claim_pending(limit=1, worker_id="worker-a")[0]
    
    event.attempts = 5  # assuming max is 5
    db.commit()
    
    service.mark_failed(event, "Temporary failure", permanent=False)
    
    db.refresh(event)
    assert event.status == "dead_letter"
    assert event.next_attempt_at is None

def test_unclaimable_before_next_attempt_at(db: Session):
    event = create_event(db)
    
    service = GitPushEventService(db)
    event = service.claim_pending(limit=1, worker_id="worker-a")[0]
    
    service.mark_failed(event, "Temporary failure", permanent=False)
    
    # Should not be claimable because next_attempt_at is in the future
    claimed = service.claim_pending(limit=1, worker_id="worker-b")
    assert len(claimed) == 0

def test_claimable_after_next_attempt_at(db: Session):
    event = create_event(db)
    
    service = GitPushEventService(db)
    event = service.claim_pending(limit=1, worker_id="worker-a")[0]
    
    service.mark_failed(event, "Temporary failure", permanent=False)
    
    # artificially move next_attempt_at to the past
    event.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    
    claimed = service.claim_pending(limit=1, worker_id="worker-b")
    assert len(claimed) == 1
    assert claimed[0].id == event.id

from app.models.git_push_event import GitPushEvent
from app.services.git_push_event_service import GitPushEventService

def test_model_status_constants_exist():
    assert GitPushEvent.STATUS_DEAD_LETTER == "dead_letter"
    assert GitPushEvent.STATUS_PENDING == "pending"
    assert GitPushEvent.STATUS_PROCESSING == "processing"
    assert GitPushEvent.STATUS_PROCESSED == "processed"
    assert GitPushEvent.STATUS_FAILED == "failed"

def test_service_constants_alias_model():
    assert GitPushEventService.STATUS_DEAD_LETTER is GitPushEvent.STATUS_DEAD_LETTER
    assert GitPushEventService.STATUS_PENDING is GitPushEvent.STATUS_PENDING
    assert GitPushEventService.STATUS_PROCESSING is GitPushEvent.STATUS_PROCESSING
    assert GitPushEventService.STATUS_PROCESSED is GitPushEvent.STATUS_PROCESSED
    assert GitPushEventService.STATUS_FAILED is GitPushEvent.STATUS_FAILED

def test_dead_letter_cannot_be_claimed(db: Session):
    event = create_event(db)
    service = GitPushEventService(db)
    service.claim_pending(worker_id="test-worker")
    service.mark_failed(event, "fatal error", permanent=True, expected_worker_id="test-worker")
    
    assert event.status == GitPushEvent.STATUS_DEAD_LETTER
    claimed = service.claim_pending(worker_id="another-worker")
    assert len(claimed) == 0

def test_dead_letter_has_no_active_lease_or_next_attempt(db: Session):
    event = create_event(db)
    service = GitPushEventService(db)
    service.claim_pending(worker_id="test-worker")
    service.mark_failed(event, "fatal error", permanent=True, expected_worker_id="test-worker")
    
    assert event.status == GitPushEvent.STATUS_DEAD_LETTER
    assert event.worker_id is None
    assert event.lease_expires_at is None
    assert event.next_attempt_at is None

def test_dead_letter_remains_dead_letter_after_worker_cycle(db: Session, monkeypatch):
    event = create_event(db)
    service = GitPushEventService(db)
    service.claim_pending(worker_id="test-worker")
    service.mark_failed(event, "fatal error", permanent=True, expected_worker_id="test-worker")
    
    db.commit()
    
    # Run a full worker cycle
    from app.services.git_push_event_worker import GitPushEventWorker
    worker = GitPushEventWorker()
    monkeypatch.setattr(
        "app.services.git_push_event_worker.SessionLocal",
        lambda: db,
    )
    worker.run_once()
    
    event = db.get(GitPushEvent, event.id)
    assert event.status == GitPushEvent.STATUS_DEAD_LETTER
    assert event.worker_id is None
