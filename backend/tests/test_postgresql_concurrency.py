import threading
import uuid
import json
import pytest
from sqlalchemy import create_engine, text, select, event, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.models.user import User
from app.models.repository import Repository
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.services.change_service import ChangeService

import os
import tempfile
from app.db.session import Base

@pytest.fixture(scope="module")
def pg_engine():
    if "sqlite" in settings.database_url.lower():
        db_fd, db_path = tempfile.mkstemp(suffix="_pg_conc.db")
        os.close(db_fd)
        temp_url = f"sqlite:///{db_path}"
        engine = create_engine(temp_url)
        Base.metadata.create_all(bind=engine)
        yield engine
        engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass
        return

    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM git_push_events"))
        conn.execute(text("DELETE FROM changes"))
    yield engine
    engine.dispose()

def test_postgresql_concurrency_race(pg_engine):
    # Setup test data in a single transaction
    SessionLocal = sessionmaker(bind=pg_engine)
    db = SessionLocal()
    
    # Create unique entities
    user_id = str(uuid.uuid4())
    username = f"user-{uuid.uuid4().hex[:8]}"
    user = User(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
    )
    db.add(user)
    db.flush()
    
    repo_id = f"repo-{uuid.uuid4().hex[:8]}"
    repo = Repository(
        id=repo_id,
        owner_id=user_id,
        name=repo_id,
        slug=repo_id.lower(),
        description="Test repo for concurrency",
        visibility="private",
        default_branch="main",
        storage_key=f"{repo_id}.git",
    )
    db.add(repo)
    db.flush()
    
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        owner_id=user_id,
        name=f"agent-{uuid.uuid4().hex[:8]}",
        description="Test agent",
        provider="test",
        model="test",
        token_hash="unused",
        token_prefix=f"sa_{uuid.uuid4().hex[:8]}", # Shorter prefix to satisfy character varying(16)
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent_id,
        type="agent",
        name=agent.name,
        owner_id=user_id,
        capabilities=(
            '["repository.read",'
            '"repository.write",'
            '"change.create"]'
        ),
    )
    db.add(actor)
    db.flush()
    
    db.commit()
    db.close()
    
    # Now set up the race between two threads
    barrier = threading.Barrier(2)
    errors = {}
    results = {}
    
    def worker_thread(worker_name, result_key):
        session = SessionLocal()
        # Mock Git methods inside ChangeService to bypass subprocess calls
        service = ChangeService(session)
        service.resolve_commit = lambda repo, commit: commit
        service._classify_ref_update = lambda repo, b, res: "update"
        service.get_changed_files = lambda repo, b, res: []
        
        # Load entities in this session
        worker_repo = session.get(Repository, repo_id)
        worker_actor = session.get(Actor, agent_id)
        
        # Track if we've already waited to avoid barrier block on subsequent flushes
        has_waited = False
        
        # Hook into before_flush to block both threads until they are both ready to flush
        @event.listens_for(session, "before_flush")
        def block_before_flush(sess, flush_context, instances):
            nonlocal has_waited
            if not has_waited:
                has_waited = True
                try:
                    # Wait for both threads to hit the first flush phase
                    barrier.wait(timeout=5)
                except Exception as e:
                    errors[worker_name] = e
                
        try:
            change = service.record_agent_push(
                repository=worker_repo,
                actor=worker_actor,
                base_commit="a" * 40,
                resulting_commit="b" * 40,
                intent=f"Concurrent intent from {worker_name}",
                metadata_json=json.dumps({"ref": "refs/heads/main"}),
                commit=True
            )
            results[result_key] = change
        except Exception as exc:
            errors[result_key] = exc
        finally:
            session.close()

    t1 = threading.Thread(target=worker_thread, args=("worker_a", "a"))
    t2 = threading.Thread(target=worker_thread, args=("worker_b", "b"))
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Assertions:
    # 1. No thread raised an unhandled exception that broke execution (errors should be empty)
    assert not errors, f"Threads encountered errors: {errors}"
    
    # 2. Both workers returned a Change
    assert "a" in results
    assert "b" in results
    
    change_a = results["a"]
    change_b = results["b"]
    
    # 3. Both workers returned the same Change.id
    assert change_a.id == change_b.id
    
    # 4. Verify only one Change exists in the DB
    verification_db = SessionLocal()
    try:
        changes = verification_db.scalars(
            select(Change).where(Change.operation_key == change_a.operation_key)
        ).all()
        assert len(changes) == 1
        assert changes[0].id == change_a.id
        
        # Explicit SQL check
        res = verification_db.execute(text("SELECT COUNT(*) FROM changes WHERE operation_key = :key"), {"key": change_a.operation_key}).scalar()
        assert res == 1
    finally:
        verification_db.close()
        
    # Cleanup setup data from the PostgreSQL DB
    cleanup_db = SessionLocal()
    try:
        cleanup_db.execute(text(f"DELETE FROM changes WHERE operation_key = '{change_a.operation_key}'"))
        cleanup_db.execute(text(f"DELETE FROM actors WHERE id = '{agent_id}'"))
        cleanup_db.execute(text(f"DELETE FROM agents WHERE id = '{agent_id}'"))
        cleanup_db.execute(text(f"DELETE FROM repositories WHERE id = '{repo_id}'"))
        cleanup_db.execute(text(f"DELETE FROM users WHERE id = '{user_id}'"))
        cleanup_db.commit()
    finally:
        cleanup_db.close()

import time
from datetime import datetime, timezone, timedelta
from app.services.git_push_event_service import GitPushEventService, LeaseLostError
from app.models.git_push_event import GitPushEvent
from app.services.git_push_event_processor import GitPushEventProcessor

def create_base_entities(db: Session):
    user_id = str(uuid.uuid4())
    username = f"user-{uuid.uuid4().hex[:8]}"
    user = User(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
    )
    db.add(user)
    db.flush()
    
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        owner_id=user_id,
        name=f"repo-{repo_id[:8]}",
        slug=f"repo-{repo_id[:8]}",
        description="Test repo",
        visibility="private",
        default_branch="main",
        storage_key=f"{repo_id}.git",
    )
    db.add(repo)
    db.flush()
    
    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        owner_id=user_id,
        name=f"agent-{uuid.uuid4().hex[:8]}",
        description="Test agent",
        provider="test",
        model="test",
        token_hash="unused",
        token_prefix=f"sa_{uuid.uuid4().hex[:8]}",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent_id,
        type="agent",
        name=agent.name,
        owner_id=user_id,
        capabilities=(
            '["repository.read",'
            '"repository.write",'
            '"change.create"]'
        ),
    )
    db.add(actor)
    db.flush()
    return user, repo, actor

def test_postgresql_stale_worker_protection(pg_engine):
    SessionLocal = sessionmaker(bind=pg_engine)
    db = SessionLocal()
    
    user, repo, actor = create_base_entities(db)
    service = GitPushEventService(db)
    
    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-a"},
        after_refs={"refs/heads/main": "commit-b"},
    )
    db.commit()
    
    event_id = event.id
    
    # Worker A claims
    claimed_a = service.claim_pending(limit=1, worker_id="worker-a")
    assert len(claimed_a) == 1
    db.commit()
    
    # Simulate lease expiration
    event_a = db.get(GitPushEvent, event_id)
    event_a.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    event_a.updated_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()
    
    # Recovery daemon recovers it
    recovered = service.recover_stale_processing(timeout_seconds=1)
    assert recovered >= 1
    db.commit()
    
    # Worker B claims
    # (Since recover_stale_processing now adds backoff, we need to artificially expire backoff first)
    event_b = db.get(GitPushEvent, event_id)
    event_b.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()
    
    claimed_b = service.claim_pending(limit=1, worker_id="worker-b")
    assert len(claimed_b) == 1
    db.commit()
    
    # Now Worker A attempts to process and finalize its stale reference
    processor_a = GitPushEventProcessor(db)
    # Mock Git methods
    processor_a.changes.resolve_commit = lambda r, c: c
    processor_a.changes._classify_ref_update = lambda r, b, a: "update"
    processor_a.changes.get_changed_files = lambda r, b, a: []
    
    event_a_stale = db.get(GitPushEvent, event_id)
    
    processed = processor_a.process_claimed_event(event_a_stale, worker_id="worker-a")
    
    # It should have rolled back due to LeaseLostError, leaving the event untouched (still processing by worker-b)
    db.expire_all()
    event_final = db.get(GitPushEvent, event_id)
    assert event_final.status == "processing"
    assert event_final.worker_id == "worker-b"
    
    db.close()

def test_postgresql_concurrent_claiming(pg_engine):
    if pg_engine.dialect.name != "postgresql":
        pytest.skip(
            "PostgreSQL row-locking test requires a PostgreSQL database"
        )

    SessionLocal = sessionmaker(bind=pg_engine)
    db = SessionLocal()
    
    user, repo, actor = create_base_entities(db)
    service = GitPushEventService(db)
    
    # Create 10 pending events
    event_ids = []
    for _ in range(10):
        event = service.create_event(
            repository=repo,
            actor=actor,
            before_refs={"refs/heads/main": "commit-a"},
            after_refs={"refs/heads/main": "commit-b"},
        )
        event_ids.append(event.id)
    db.commit()
    db.close()
    
    barrier = threading.Barrier(2)
    claimed_by_worker = {"worker-1": [], "worker-2": []}
    
    def worker_thread(worker_name):
        session = SessionLocal()
        service = GitPushEventService(session)
        barrier.wait(timeout=5)
        # Try to claim all 10
        claimed = service.claim_pending(limit=10, worker_id=worker_name)
        session.commit()
        claimed_by_worker[worker_name] = [e.id for e in claimed]
        session.close()

    t1 = threading.Thread(target=worker_thread, args=("worker-1",))
    t2 = threading.Thread(target=worker_thread, args=("worker-2",))
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Verify no overlaps
    set1 = set(claimed_by_worker["worker-1"])
    set2 = set(claimed_by_worker["worker-2"])
    
    assert len(set1.intersection(set2)) == 0
    # Together they should have claimed at least the 10 we created
    assert len(set1) + len(set2) >= 10


def test_postgresql_crash_after_change_creation(pg_engine):
    SessionLocal = sessionmaker(bind=pg_engine)
    db = SessionLocal()
    
    user, repo, actor = create_base_entities(db)
    service = GitPushEventService(db)
    
    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-c"},
        after_refs={"refs/heads/main": "commit-d"},
    )
    db.commit()
    
    event_id = event.id
    
    # Claim the event
    claimed = service.claim_pending(limit=1, worker_id="worker-crash")
    assert len(claimed) == 1
    db.commit()
    
    # Simulate partial processor execution (Change created, but crash before finalization)
    processor = GitPushEventProcessor(db)
    processor.changes.resolve_commit = lambda r, c: c
    processor.changes._classify_ref_update = lambda r, b, a: "update"
    processor.changes.get_changed_files = lambda r, b, a: []
    
    # Create the change directly to simulate crash
    change = processor.changes.record_agent_push(
        repository=repo,
        actor=actor,
        base_commit="commit-c",
        resulting_commit="commit-d",
        intent="Test crash",
        metadata_json=json.dumps({"ref": "refs/heads/main"}),
        commit=True
    )
    db.commit()
    change_id = change.id
    
    # Worker dies, lease expires
    event_crash = db.get(GitPushEvent, event_id)
    event_crash.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    event_crash.updated_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()
    
    # Recovery daemon recovers it
    service.recover_stale_processing(timeout_seconds=1)
    db.commit()
    
    event_crash.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()
    
    # New worker claims
    claimed_new = service.claim_pending(limit=1, worker_id="worker-new")
    assert len(claimed_new) == 1
    db.commit()
    
    # New worker processes it
    processor_new = GitPushEventProcessor(db)
    processor_new.changes.resolve_commit = lambda r, c: c
    processor_new.changes._classify_ref_update = lambda r, b, a: "update"
    processor_new.changes.get_changed_files = lambda r, b, a: []
    
    processed = processor_new.process_claimed_event(claimed_new[0], worker_id="worker-new")
    
    # Check that event was successful
    assert processed.status == "processed"
    
    # Check that it found the existing Change and didn't create a new one
    db.expire_all()
    count = db.execute(text("SELECT COUNT(*) FROM changes WHERE operation_key = :key"), {"key": change.operation_key}).scalar()
    assert count == 1
    
    db.close()

def test_postgresql_retry_dead_letter_state_machine(pg_engine):
    SessionLocal = sessionmaker(bind=pg_engine)
    db = SessionLocal()
    
    user, repo, actor = create_base_entities(db)
    service = GitPushEventService(db)
    
    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "commit-e"},
        after_refs={"refs/heads/main": "commit-f"},
    )
    db.commit()
    
    # 5 attempts limit
    for attempt in range(1, 6):
        # Move next_attempt_at to past so it's claimable
        event_db = db.get(GitPushEvent, event.id)
        if event_db.next_attempt_at:
            event_db.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        db.commit()
        
        claimed = service.claim_pending(limit=1, worker_id=f"worker-retry-{attempt}")
        assert len(claimed) == 1
        db.commit()
        
        processor = GitPushEventProcessor(db)
        def failing_processor(*args, **kwargs):
            raise Exception(f"Transient failure {attempt}")
            
        processor.changes.record_agent_push = failing_processor
        processor.process_claimed_event(claimed[0], worker_id=f"worker-retry-{attempt}")
        
        db.expire_all()
        refreshed = db.get(GitPushEvent, event.id)
        
        if attempt < 5:
            assert refreshed.status == "failed"
            assert refreshed.attempts == attempt
            assert refreshed.next_attempt_at is not None
        else:
            assert refreshed.status == "dead_letter"
            assert refreshed.attempts == 5
            assert refreshed.next_attempt_at is None
    
    db.close()
