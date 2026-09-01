import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.change_service import ChangeService


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


def make_user(db: Session):
    user = User(
        id=str(uuid.uuid4()),
        username=f"user-{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex}@example.com",
        password_hash="unused",
    )

    db.add(user)
    db.flush()

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


def make_repository(
    db: Session,
    owner_id: str,
):
    repository = Repository(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name="test-repository",
        slug=f"repo-{uuid.uuid4().hex[:8]}",
        description="Test repository",
        visibility="private",
        default_branch="main",
        storage_key=f"{uuid.uuid4().hex}.git",
    )

    db.add(repository)
    db.flush()

    return repository


def make_agent_actor(
    db: Session,
    owner_id: str,
    capabilities: list[str],
    repository: Repository | None = None,
):
    agent_id = str(uuid.uuid4())

    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name="Test Agent",
        token_hash="unused",
        token_prefix="sutra_agent_test",
        status="active",
        is_active=True,
    )

    actor = Actor(
        id=agent_id,
        type="agent",
        name="Test Agent",
        owner_id=owner_id,
        capabilities=json.dumps(capabilities),
    )

    db.add(agent)
    db.add(actor)
    db.flush()

    if repository is not None:
        from app.models.agent_repository_access import AgentRepositoryAccess
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps(capabilities),
            enabled=True,
        )
        db.add(access)
        db.flush()

    return agent, actor


def test_agent_without_write_cannot_record_push(
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)

    _, actor = make_agent_actor(
        db,
        user.id,
        [
            AuthorizationService.READ,
            AuthorizationService.CHANGE_CREATE,
            AuthorizationService.CHANGE_COMMIT,
        ],
        repository=repository,
    )

    service = ChangeService(db)

    monkeypatch.setattr(
        service,
        "resolve_commit",
        lambda repository, commit: commit,
    )

    with pytest.raises(
        PermissionError,
        match="repository.write",
    ):
        service.record_agent_push(
            repository=repository,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Unauthorized push",
            metadata_json='{"ref":"refs/heads/main"}',
        )


def test_agent_without_change_create_cannot_record_push(
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)

    _, actor = make_agent_actor(
        db,
        user.id,
        [
            AuthorizationService.READ,
            AuthorizationService.WRITE,
            AuthorizationService.CHANGE_COMMIT,
        ],
        repository=repository,
    )

    service = ChangeService(db)
    
    monkeypatch.setattr(
        service,
        "resolve_commit",
        lambda repository, commit: commit,
    )

    with pytest.raises(
        PermissionError,
        match="change.create",
    ):
        service.record_agent_push(
            repository=repository,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Unauthorized change creation",
            metadata_json='{"ref":"refs/heads/main"}',
        )


def test_agent_with_write_and_create_can_enter_push_path(
    db,
    monkeypatch,
):
    user = make_user(db)
    repository = make_repository(db, user.id)

    _, actor = make_agent_actor(
        db,
        user.id,
        [
            AuthorizationService.READ,
            AuthorizationService.WRITE,
            AuthorizationService.CHANGE_CREATE,
        ],
        repository=repository,
    )

    service = ChangeService(db)

    monkeypatch.setattr(
        service,
        "resolve_commit",
        lambda repository, commit: commit,
    )

    monkeypatch.setattr(
        service,
        "_classify_ref_update",
        lambda repository, before, after: "update",
    )

    monkeypatch.setattr(
        service,
        "get_changed_files",
        lambda repository, before, after: [],
    )

    monkeypatch.setattr(
        "app.services.change_service.ChangePolicyService.evaluate",
        lambda self, change: type(
            "Policy",
            (),
            {
                "decision": "review",
                "reason": "Review required",
                "conflict_level": "none",
                "related_change_ids": [],
                "dependency_count": 0,
            },
        )(),
    )

    change = service.record_agent_push(
        repository=repository,
        actor=actor,
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        intent="Authorized push",
        metadata_json='{"ref":"refs/heads/main"}',
    )

    assert change.actor_id == actor.id
    assert change.status == "proposed"