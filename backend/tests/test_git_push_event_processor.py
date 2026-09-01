from datetime import datetime, timezone
from app.models import Change
import uuid
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.actor import Actor
from app.models.repository import Repository
from app.models.user import User
from app.models.agent import Agent
from app.models.git_push_event import GitPushEvent
from app.services.git_push_event_service import GitPushEventService
from app.services.git_push_event_processor import GitPushEventProcessor
from app.services.change_service import ChangeService
from app.services.change_policy_service import PolicyDecision, ChangePolicyService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def mock_git_and_policy(monkeypatch):
    # Mock Git operations on ChangeService
    monkeypatch.setattr(ChangeService, "resolve_commit", lambda self, repo, commit: commit)
    monkeypatch.setattr(ChangeService, "_classify_ref_update", lambda self, repo, b, res: "update")
    monkeypatch.setattr(ChangeService, "get_changed_files", lambda self, repo, b, res: [])

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
    if not db.get(Actor, user.id):
        actor = Actor(
            id=user.id,
            owner_id=user.id,
            type="human",
            name=user.username,
            capabilities='["repository.read", "repository.write", "change.create"]',
        )
        db.add(actor)
        db.flush()
    return user


def make_repository(db: Session, owner_id: str) -> Repository:
    repository_id = f"repo-{uuid.uuid4().hex[:8]}"
    repository = Repository(
        id=repository_id,
        owner_id=owner_id,
        name=repository_id,
        slug=repository_id.lower(),
        description="Test repo",
        visibility="private",
        default_branch="main",
        storage_key=f"{repository_id}.git",
    )
    db.add(repository)
    db.flush()
    return repository


def make_agent_actor(
    db: Session,
    owner_id: str,
    *,
    agent_id: str | None = None,
    is_active: bool = True,
    agent_status: str = "active",
):
    agent_id = agent_id or str(uuid.uuid4())

    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name=f"agent-{uuid.uuid4().hex[:8]}",
        description="Test agent",
        provider="test",
        model="test",
        token_hash="unused",
        token_prefix=f"sutra_agent_{uuid.uuid4().hex[:8]}",
        status=agent_status,
        is_active=is_active,
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

    return agent, actor


def test_claim_pending_limits(db: Session):
    service = GitPushEventService(db)

    with pytest.raises(ValueError, match="Limit must be positive"):
        service.claim_pending(limit=0)

    with pytest.raises(ValueError, match="Limit cannot exceed 1000"):
        service.claim_pending(limit=1001)


def test_claim_pending_empty(db: Session):
    service = GitPushEventService(db)
    events = service.claim_pending(limit=10)
    assert len(events) == 0


def test_claim_pending_success(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(db, user.id)

    service = GitPushEventService(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-a"},
        after_refs={"refs/heads/main": "commit-b"},
    )
    db.commit()

    claimed = service.claim_pending(limit=10)
    assert len(claimed) == 1
    assert claimed[0].id == event.id
    assert claimed[0].status == GitPushEventService.STATUS_PROCESSING
    assert claimed[0].attempts == 1


def test_process_claimed_event_success(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(db, user.id)

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-a"},
        after_refs={"refs/heads/main": "commit-b"},
    )
    db.commit()

    claimed = service.claim_pending(limit=10)
    assert len(claimed) == 1

    processed_event = processor.process_claimed_event(claimed[0])
    assert processed_event.status == GitPushEventService.STATUS_PROCESSED
    assert processed_event.last_error is None


def test_process_claimed_event_repo_missing(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(db, user.id)

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-a"},
        after_refs={"refs/heads/main": "commit-b"},
    )
    db.commit()

    # Soft-delete the repository to trigger failure
    repo.deleted_at = datetime.now(timezone.utc)
    db.commit()

    claimed = service.claim_pending(limit=10)
    assert len(claimed) == 1

    processed_event = processor.process_claimed_event(claimed[0])
    assert processed_event.status == GitPushEventService.STATUS_DEAD_LETTER
    assert "Repository no longer exists" in processed_event.last_error


def test_process_pending_flow(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(db, user.id)

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event1 = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-a"},
        after_refs={"refs/heads/main": "commit-b"},
    )
    event2 = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/feature": "commit-c"},
        after_refs={"refs/heads/feature": "commit-d"},
    )
    db.commit()

    processed = processor.process_pending(limit=10)
    assert len(processed) == 2
    assert processed[0].status == GitPushEventService.STATUS_PROCESSED
    assert processed[1].status == GitPushEventService.STATUS_PROCESSED

def test_revoked_agent_event_is_not_converted_to_change(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    agent.is_active = False
    agent.status = "revoked"
    db.commit()

    claimed = service.claim_pending(limit=10)

    assert len(claimed) == 1

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        "Agent is inactive"
        in processed.last_error
    )

    from app.models.change import Change

    changes = db.query(Change).all()

    assert changes == []


def test_inactive_agent_event_is_not_converted_to_change(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)

    agent, actor = make_agent_actor(
        db,
        user.id,
        is_active=False,
        agent_status="active",
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    claimed = service.claim_pending(limit=10)

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        "Agent is inactive"
        in processed.last_error
    )

    from app.models.change import Change

    assert db.query(Change).count() == 0


def test_agent_status_non_active_event_is_rejected(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)

    agent, actor = make_agent_actor(
        db,
        user.id,
        is_active=True,
        agent_status="suspended",
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    claimed = service.claim_pending(limit=10)

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        "Agent is not active"
        in processed.last_error
    )

    from app.models.change import Change

    assert db.query(Change).count() == 0


def test_multi_ref_push_creates_one_change_per_changed_ref(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
            "refs/heads/feature": "commit-c",
        },
        after_refs={
            "refs/heads/main": "commit-b",
            "refs/heads/feature": "commit-d",
        },
    )

    db.commit()

    claimed = service.claim_pending(limit=10)

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_PROCESSED
    )

    from app.models.change import Change

    changes = db.query(Change).all()

    assert len(changes) == 2

    refs = {
        json.loads(change.metadata_json)["ref"]
        for change in changes
    }

    assert refs == {
        "refs/heads/main",
        "refs/heads/feature",
    }


def test_deleted_ref_does_not_create_change(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/feature": "commit-a",
        },
        after_refs={},
    )

    db.commit()

    claimed = service.claim_pending(limit=10)

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_PROCESSED
    )

    from app.models.change import Change

    assert db.query(Change).count() == 0


def test_processing_same_event_twice_is_idempotent(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    claimed = service.claim_pending(limit=10)

    assert len(claimed) == 1

    first = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        first.status
        == GitPushEventService.STATUS_PROCESSED
    )

    from app.models.change import Change

    assert db.query(Change).count() == 1

    second = processor.process_event(
        event.id
    )

    assert (
        second.status
        == GitPushEventService.STATUS_PROCESSED
    )

    assert db.query(Change).count() == 1


def test_multi_ref_failure_rolls_back_all_changes(
    db: Session,
    monkeypatch,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
            "refs/heads/feature": "commit-c",
        },
        after_refs={
            "refs/heads/main": "commit-b",
            "refs/heads/feature": "commit-d",
        },
    )

    db.commit()

    claimed = service.claim_pending(limit=10)

    original_record = processor.changes.record_agent_push
    call_count = 0

    def mock_record(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("Simulated failure on second ref")
        return original_record(*args, **kwargs)

    monkeypatch.setattr(
        processor.changes,
        "record_agent_push",
        mock_record,
    )

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_FAILED
    )

    assert (
        "Simulated failure on second ref"
        in processed.last_error
    )

    from app.models.change import Change

    # Nothing should be committed
    assert db.query(Change).count() == 0


def test_event_actor_tampering_is_rejected(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)

    actor = Actor(
        id=str(uuid.uuid4()),
        type="agent",
        name="original-agent",
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )

    attacker = Actor(
        id=str(uuid.uuid4()),
        type="agent",
        name="attacker-agent",
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )

    db.add(actor)
    db.add(attacker)
    db.flush()

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    # Tamper with the event after its integrity hash
    # has already been persisted.
    event.actor_id = attacker.id
    db.flush()

    claimed = service.claim_pending(limit=10)

    assert len(claimed) == 1

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        processed.last_error
        == "Git push event integrity verification failed"
    )


def test_event_integrity_actor_tampering_is_rejected(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)

    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    attacker = make_agent_actor(
        db,
        user.id,
    )[1]

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    event.actor_id = attacker.id
    db.flush()

    claimed = service.claim_pending(
        limit=10
    )

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        "integrity verification failed"
        in processed.last_error
    )


def test_event_integrity_repository_tampering_is_rejected(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)

    attacker_repo = make_repository(
        db,
        user.id,
    )

    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    db.commit()

    event.repository_id = attacker_repo.id
    db.flush()

    claimed = service.claim_pending(
        limit=10
    )

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        "integrity verification failed"
        in processed.last_error
    )


def test_event_created_with_integrity_hash(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(
        db,
        user.id,
    )

    service = GitPushEventService(db)

    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={
            "refs/heads/main": "commit-a",
        },
        after_refs={
            "refs/heads/main": "commit-b",
        },
    )

    assert event.integrity_version == 2
    assert event.integrity_hash
    assert len(event.integrity_hash) == 64

    service.verify_integrity(event)

def test_event_repository_tampering_is_rejected(
    db: Session,
):
    user = make_user(db)

    repository = make_repository(
        db,
        user.id,
    )

    attacker_repository = make_repository(
        db,
        user.id,
    )

    actor = Actor(
        id=str(uuid.uuid4()),
        type="agent",
        name="test-agent",
        owner_id=user.id,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )

    db.add(actor)
    db.flush()

    service = GitPushEventService(db)
    processor = GitPushEventProcessor(db)

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

    # Tamper with repository ownership reference after
    # the integrity hash has already been persisted.
    event.repository_id = attacker_repository.id
    db.flush()

    claimed = service.claim_pending(limit=10)

    assert len(claimed) == 1

    processed = processor.process_claimed_event(
        claimed[0]
    )

    assert (
        processed.status
        == GitPushEventService.STATUS_DEAD_LETTER
    )

    assert (
        processed.last_error
        == "Git push event integrity verification failed"
    )

def test_operation_key_is_deterministic(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_agent_actor(db, user.id)

    service = ChangeService(db)

    key1 = service._git_push_operation_key(
        repository=repo,
        actor=actor,
        ref="refs/heads/main",
        before_commit="a" * 40,
        after_commit="b" * 40,
    )

    key2 = service._git_push_operation_key(
        repository=repo,
        actor=actor,
        ref="refs/heads/main",
        before_commit="a" * 40,
        after_commit="b" * 40,
    )

    assert key1 == key2
    assert len(key1) == 64
    assert all(
        character in "0123456789abcdef"
        for character in key1
    )


def test_operation_key_changes_when_ref_changes(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_agent_actor(db, user.id)

    service = ChangeService(db)

    main_key = service._git_push_operation_key(
        repo,
        actor,
        "refs/heads/main",
        "a" * 40,
        "b" * 40,
    )

    feature_key = service._git_push_operation_key(
        repo,
        actor,
        "refs/heads/feature",
        "a" * 40,
        "b" * 40,
    )

    assert main_key != feature_key


def test_operation_key_changes_when_commit_changes(db: Session):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_agent_actor(db, user.id)

    service = ChangeService(db)

    key1 = service._git_push_operation_key(
        repo,
        actor,
        "refs/heads/main",
        "a" * 40,
        "b" * 40,
    )

    key2 = service._git_push_operation_key(
        repo,
        actor,
        "refs/heads/main",
        "a" * 40,
        "c" * 40,
    )

    assert key1 != key2


def test_duplicate_agent_push_returns_same_change(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_agent_actor(db, user.id)

    service = ChangeService(db)

    first = service.record_agent_push(
        repository=repo,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Duplicate test",
        risk_level="low",
        metadata_json=json.dumps(
            {
                "ref": "refs/heads/main",
            }
        ),
    )

    second = service.record_agent_push(
        repository=repo,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Duplicate test",
        risk_level="low",
        metadata_json=json.dumps(
            {
                "ref": "refs/heads/main",
            }
        ),
    )

    assert first.id == second.id
    assert first.operation_key == second.operation_key

    changes = db.query(Change).all()

    assert len(changes) == 1


def test_force_update_is_rejected(
    db: Session,
    monkeypatch,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    actor = make_agent_actor(db, user.id)

    service = ChangeService(db)

    monkeypatch.setattr(
        service,
        "resolve_commit",
        lambda repository, commit: commit,
    )

    monkeypatch.setattr(
        service,
        "_classify_ref_update",
        lambda repository, before, after: "force_update",
    )

    with pytest.raises(
        ValueError,
        match="force update is not permitted",
    ):
        service.record_agent_push(
            repository=repo,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Force update",
            metadata_json=json.dumps(
                {
                    "ref": "refs/heads/main",
                }
            ),
        )
def test_concurrent_duplicate_operation_key_is_database_safe(
    db: Session,
    ):
        user = make_user(db)
        repo = make_repository(db, user.id)
        agent, actor = make_agent_actor(db, user.id)

        service = ChangeService(db)

        operation_key = service._git_push_operation_key(
            repository=repo,
            actor=actor,
            ref="refs/heads/main",
            before_commit="a" * 40,
            after_commit="b" * 40,
        )

        first = service.record_agent_push(
            repository=repo,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Concurrent operation",
            metadata_json=json.dumps(
                {
                    "ref": "refs/heads/main",
                }
            ),
        )

        second = service.record_agent_push(
            repository=repo,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Concurrent operation",
            metadata_json=json.dumps(
                {
                    "ref": "refs/heads/main",
                }
            ),
        )

        assert first.id == second.id
        assert first.operation_key == operation_key
        assert second.operation_key == operation_key

        assert (
            db.query(Change)
            .filter(
                Change.operation_key == operation_key
            )
            .count()
            == 1
    )
def test_operation_key_database_uniqueness(
    db: Session,
    ):
        user = make_user(db)
        repo = make_repository(db, user.id)
        agent, actor = make_agent_actor(db, user.id)

        service = ChangeService(db)

        first = service.record_agent_push(
            repository=repo,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Database uniqueness test",
            metadata_json=json.dumps(
                {
                    "ref": "refs/heads/main",
                }
            ),
        )

        assert first.operation_key

        duplicate = Change(
            repository_id=repo.id,
            actor_id=actor.id,
            intent="Intentional duplicate",
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            operation_key=first.operation_key,
            status="proposed",
            risk_level="unknown",
            metadata_json="{}",
        )

        db.add(duplicate)

        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()

        assert (
            db.query(Change)
            .filter(
                Change.operation_key == first.operation_key
            )
            .count()
            == 1
    )
def test_two_independent_sessions_preserve_operation_uniqueness(
    db: Session,
):
    user = make_user(db)
    repo = make_repository(db, user.id)
    agent, actor = make_agent_actor(db, user.id)

    # IMPORTANT:
    # Use the same engine/bind as the test fixture.
    # The global application engine may point at a
    # completely different database.
    bind = db.get_bind()

    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(
        bind=bind,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    # Commit fixture-created data before opening the
    # independent worker sessions.
    db.commit()

    session_a = SessionLocal()
    session_b = SessionLocal()

    try:
        repo_a = session_a.get(
            Repository,
            repo.id,
        )
        actor_a = session_a.get(
            Actor,
            actor.id,
        )

        repo_b = session_b.get(
            Repository,
            repo.id,
        )
        actor_b = session_b.get(
            Actor,
            actor.id,
        )

        assert repo_a is not None
        assert actor_a is not None
        assert repo_b is not None
        assert actor_b is not None

        service_a = ChangeService(session_a)
        service_b = ChangeService(session_b)

        # Deterministic Git behavior for the test.
        service_a.resolve_commit = (
            lambda repository, commit: commit
        )

        service_b.resolve_commit = (
            lambda repository, commit: commit
        )

        service_a._classify_ref_update = (
            lambda repository, before, after: "update"
        )

        service_b._classify_ref_update = (
            lambda repository, before, after: "update"
        )

        operation_key = (
            service_a._git_push_operation_key(
                repository=repo_a,
                actor=actor_a,
                ref="refs/heads/main",
                before_commit="a" * 40,
                after_commit="b" * 40,
            )
        )

        change_a = service_a.record_agent_push(
            repository=repo_a,
            actor=actor_a,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Concurrent worker A",
            metadata_json=json.dumps(
                {
                    "ref": "refs/heads/main",
                }
            ),
        )

        change_b = service_b.record_agent_push(
            repository=repo_b,
            actor=actor_b,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Concurrent worker B",
            metadata_json=json.dumps(
                {
                    "ref": "refs/heads/main",
                }
            ),
        )

        assert change_a.operation_key == operation_key
        assert change_b.operation_key == operation_key

        assert change_a.id == change_b.id

        verification = SessionLocal()

        try:
            changes = (
                verification.query(Change)
                .filter(
                    Change.operation_key
                    == operation_key
                )
                .all()
            )

            assert len(changes) == 1
            assert changes[0].id == change_a.id

        finally:
            verification.close()

    finally:
        session_a.close()
        session_b.close()
