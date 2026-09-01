import json
from types import SimpleNamespace
from uuid import uuid4

from app.models.actor import Actor
from app.models.repository import Repository
from app.core.security import password_hash
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.user import User
from app.services.authorization_service import AuthorizationService


def _user(db, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=password_hash.hash(
            "TestPassword123!"
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _agent(db, owner: User, name: str) -> Agent:
    agent = Agent(
        owner_id=owner.id,
        name=name,
        token_hash=password_hash.hash(
            "sutra-agent-test-token"
        ),
        token_prefix="sutra_agent_t",
        status="active",
        is_active=True,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


def test_agent_repository_access_allows_granted_capability(
    db,
):
    owner = _user(
        db,
        "agent-permission-owner",
    )

    agent = _agent(
        db,
        owner,
        "Permission Test Agent",
    )

    different_owner = _user(
        db,
        "agent-permission-repo-owner",
    )

    repository = Repository(
        id=str(uuid4()),
        owner_id=different_owner.id,
        name="permission-test-repository",
        slug="permission-test-repository",
        description="Repository used for agent access authorization test",
        visibility="private",
        default_branch="main",
        storage_key=f"test-{uuid4().hex}",
    )

    db.add(repository)
    db.flush()

    db.add(
        AgentRepositoryAccess(
            id="access-1",
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps(
                ["repository.read"]
            ),
            enabled=True,
        )
    )
    db.commit()

    decision = AuthorizationService.check(
        actor=SimpleNamespace(
            id=agent.id,
            type="agent",
            owner_id=agent.owner_id,
            capabilities="[]",
        ),
        repository=repository,
        capability=AuthorizationService.READ,
        db=db,
    )

    assert decision.allowed is True


def test_agent_repository_access_denies_ungranted_capability(
    db,
):
    owner = _user(
        db,
        "agent-permission-deny-owner",
    )

    agent = _agent(
        db,
        owner,
        "Permission Deny Agent",
    )

    different_owner = _user(
        db,
        "agent-permission-repo-owner-2",
    )

    repository = Repository(
        id=str(uuid4()),
        owner_id=different_owner.id,
        name="permission-deny-repository",
        slug="permission-deny-repository",
        description="Repository used for denied agent access authorization test",
        visibility="private",
        default_branch="main",
        storage_key=f"test-{uuid4().hex}",
    )

    db.add(repository)
    db.flush()

    db.add(
        AgentRepositoryAccess(
            id="access-2",
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps(
                ["repository.read"]
            ),
            enabled=True,
        )
    )
    db.commit()

    decision = AuthorizationService.check(
        actor=SimpleNamespace(
            id=agent.id,
            type="agent",
            owner_id=agent.owner_id,
            capabilities="[]",
        ),
        repository=repository,
        capability=AuthorizationService.CHANGE_CREATE,
        db=db,
    )

    assert decision.allowed is False