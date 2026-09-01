import json
import uuid

import pytest
from fastapi import status
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.api.agent_dependencies import create_agent_session
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.change import Change
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.change_service import ChangeService
from app.services.pull_request_service import PullRequestService


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


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


def make_user(db: Session, username_prefix: str = "user"):
    user = User(
        id=str(uuid.uuid4()),
        username=f"{username_prefix}_{uuid.uuid4().hex[:8]}",
        email=f"{username_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.flush()

    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "change.review",
            "change.approve",
        ]),
    )
    db.add(actor)
    db.flush()

    return user


def make_repository(db: Session, owner_id: str, name: str, visibility: str = "public"):
    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name=name,
        slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}",
        description=f"{name} repo",
        visibility=visibility,
        default_branch="main",
        storage_key=f"{uuid.uuid4().hex}.git",
    )
    db.add(repo)
    db.flush()
    return repo


def make_agent(db: Session, owner_id: str, name: str = "TestAgent"):
    agent_id = str(uuid.uuid4())
    raw_token = f"tok_{uuid.uuid4().hex}_sutra"
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name=name,
        token_prefix=raw_token[:16],
        token_hash=hash_password(raw_token),
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent_id,
        owner_id=owner_id,
        type="agent",
        name=name,
        capabilities=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "knowledge_graph.read",
            "knowledge_graph.write",
        ]),
    )
    db.add(actor)
    db.flush()
    return agent, actor, raw_token


def grant_repo_access(db: Session, agent_id: str, repo_id: str, permissions: list[str] | None = None, enabled: bool = True):
    if permissions is None:
        permissions = [
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "knowledge_graph.read",
            "knowledge_graph.write",
        ]
    access = AgentRepositoryAccess(
        agent_id=agent_id,
        repository_id=repo_id,
        permissions=json.dumps(permissions),
        enabled=enabled,
    )
    db.add(access)
    db.flush()
    return access


# -----------------------------------------------------------------------------
# 1. Agent + grant + public repo -> ALLOW
# -----------------------------------------------------------------------------
def test_agent_with_grant_on_public_repo_is_allowed(db: Session):
    owner = make_user(db, "owner")
    repo = make_repository(db, owner.id, "public-repo-a", visibility="public")
    agent, actor, _ = make_agent(db, owner.id, "AgentA")
    grant_repo_access(db, agent.id, repo.id)

    decision = AuthorizationService.check(
        actor=actor,
        repository=repo,
        capability=AuthorizationService.READ,
        db=db,
    )
    assert decision.allowed is True

    decision_write = AuthorizationService.check(
        actor=actor,
        repository=repo,
        capability=AuthorizationService.WRITE,
        db=db,
    )
    assert decision_write.allowed is True


# -----------------------------------------------------------------------------
# 2. Agent + NO grant + public repo -> READ DENIED & PUSH DENIED
# -----------------------------------------------------------------------------
def test_agent_without_grant_on_public_repo_is_denied_read_and_write(db: Session):
    owner = make_user(db, "owner")
    repo_a = make_repository(db, owner.id, "repo-a", visibility="public")
    repo_b = make_repository(db, owner.id, "public-repo-b", visibility="public")
    agent, actor, _ = make_agent(db, owner.id, "AgentA")
    # Grant only for Repo A
    grant_repo_access(db, agent.id, repo_a.id)

    # Repo B is public, but Agent has NO grant for Repo B
    read_decision = AuthorizationService.check(
        actor=actor,
        repository=repo_b,
        capability=AuthorizationService.READ,
        db=db,
    )
    assert read_decision.allowed is False

    write_decision = AuthorizationService.check(
        actor=actor,
        repository=repo_b,
        capability=AuthorizationService.WRITE,
        db=db,
    )
    assert write_decision.allowed is False


# -----------------------------------------------------------------------------
# 3. Agent + grant for Repo A -> Repo B public access DENIED
# -----------------------------------------------------------------------------
def test_agent_grant_repo_a_cannot_access_public_repo_b(db: Session):
    user1 = make_user(db, "user1")
    user2 = make_user(db, "user2")
    repo_a = make_repository(db, user1.id, "repo-a", visibility="private")
    repo_b = make_repository(db, user2.id, "repo-b-public", visibility="public")
    agent, actor, _ = make_agent(db, user1.id, "AgentA")
    grant_repo_access(db, agent.id, repo_a.id)

    decision = AuthorizationService.check(
        actor=actor,
        repository=repo_b,
        capability=AuthorizationService.READ,
        db=db,
    )
    assert decision.allowed is False
    assert "explicit access" in decision.reason.lower() or "missing" in decision.reason.lower()


# -----------------------------------------------------------------------------
# 4. Same human owns Repo A & B -> Agent still only accesses Repo A
# -----------------------------------------------------------------------------
def test_same_human_owner_does_not_bypass_agent_scoping(db: Session):
    owner = make_user(db, "same_owner")
    repo_a = make_repository(db, owner.id, "owner-repo-a", visibility="public")
    repo_b = make_repository(db, owner.id, "owner-repo-b", visibility="public")
    agent, actor, _ = make_agent(db, owner.id, "ScopedAgent")
    grant_repo_access(db, agent.id, repo_a.id)

    # Allowed on Repo A
    assert AuthorizationService.check(actor, repo_a, AuthorizationService.READ, db).allowed is True
    assert AuthorizationService.check(actor, repo_a, AuthorizationService.WRITE, db).allowed is True

    # Strictly DENIED on Repo B even though owner is identical and repo is public
    assert AuthorizationService.check(actor, repo_b, AuthorizationService.READ, db).allowed is False
    assert AuthorizationService.check(actor, repo_b, AuthorizationService.WRITE, db).allowed is False


# -----------------------------------------------------------------------------
# 5. Remove grant -> Agent loses access. Restore grant -> Agent access restored.
# -----------------------------------------------------------------------------
def test_dynamic_grant_revocation_and_restoration(db: Session):
    owner = make_user(db, "owner")
    repo = make_repository(db, owner.id, "dynamic-repo", visibility="public")
    agent, actor, _ = make_agent(db, owner.id, "DynamicAgent")
    access = grant_repo_access(db, agent.id, repo.id)

    # 1. Active grant -> ALLOW
    assert AuthorizationService.check(actor, repo, AuthorizationService.READ, db).allowed is True

    # 2. Disable grant -> DENY
    access.enabled = False
    db.flush()
    assert AuthorizationService.check(actor, repo, AuthorizationService.READ, db).allowed is False

    # 3. Restore grant -> ALLOW
    access.enabled = True
    db.flush()
    assert AuthorizationService.check(actor, repo, AuthorizationService.READ, db).allowed is True


# -----------------------------------------------------------------------------
# 6. Human access to public repo -> PRESERVED
# -----------------------------------------------------------------------------
def test_human_access_to_public_repo_is_preserved(db: Session, client: TestClient):
    owner = make_user(db, "repo_owner")
    other_human = make_user(db, "other_human")
    public_repo = make_repository(db, owner.id, "public-repo-test", visibility="public")

    # In git_http transport authorization
    from app.api.git_http import GitPrincipal, authorize_repository_access
    human_principal = GitPrincipal(
        kind="human",
        username=other_human.username,
        user=other_human,
    )

    # Human can read public repo
    authorize_repository_access(
        principal=human_principal,
        repository=public_repo,
        repository_owner=owner,
        db=db,
        capability=AuthorizationService.READ,
    )

    # Human cannot push to someone else's public repo
    with pytest.raises(Exception):
        authorize_repository_access(
            principal=human_principal,
            repository=public_repo,
            repository_owner=owner,
            db=db,
            capability=AuthorizationService.WRITE,
        )


# -----------------------------------------------------------------------------
# 7. KG / Change / PR creation on public repo without grant -> DENIED
# -----------------------------------------------------------------------------
def test_agent_cannot_perform_change_pr_or_kg_on_public_repo_without_grant(db: Session, monkeypatch):
    owner = make_user(db, "owner")
    repo_a = make_repository(db, owner.id, "repo-a", visibility="private")
    repo_b = make_repository(db, owner.id, "repo-b-public", visibility="public")
    agent, actor, _ = make_agent(db, owner.id, "AgentMulti")
    grant_repo_access(db, agent.id, repo_a.id)

    # 1. Knowledge Graph Read & Write
    assert AuthorizationService.check(actor, repo_b, AuthorizationService.KNOWLEDGE_GRAPH_READ, db).allowed is False
    assert AuthorizationService.check(actor, repo_b, AuthorizationService.KNOWLEDGE_GRAPH_WRITE, db).allowed is False

    # 2. Change Service record_agent_push
    change_svc = ChangeService(db)
    monkeypatch.setattr(change_svc, "resolve_commit", lambda r, c: c)

    with pytest.raises(PermissionError):
        change_svc.record_agent_push(
            repository=repo_b,
            actor=actor,
            base_commit="a" * 40,
            resulting_commit="b" * 40,
            intent="Agent unauthorized push to public repo",
            metadata_json='{"ref":"refs/heads/main"}',
        )

    # 3. Pull Request creation
    pr_svc = PullRequestService(db)
    dummy_change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo_b.id,
        actor_id=actor.id,
        intent="Dummy change",
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        operation_key=(uuid.uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(dummy_change)
    db.flush()

    with pytest.raises(PermissionError):
        pr_svc.create_pull_request(
            repository_id=repo_b.id,
            author_id=actor.id,
            source_change_id=dummy_change.id,
            title="Unauthorized PR",
            target_branch="main",
        )
