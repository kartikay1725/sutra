import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.agent_dependencies import get_current_agent
from app.api.dependencies import get_current_user
from app.db.session import Base, get_db
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.repository import Repository
from app.models.user import User
from app.services.change_policy_service import PolicyDecision
from app.services.change_service import ChangeService


TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


BASE_COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
RESULTING_COMMIT = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def setup_fixtures(db):
    user = User(
        id="user-1",
        username="testuser",
        email="testuser@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)

    agent = Agent(
        id="agent-1",
        owner_id="user-1",
        name="Test Agent",
        description="Test agent",
        provider="test",
        model="test",
        token_hash="hash",
        token_prefix="pref",
        status="active",
        is_active=True,
    )
    db.add(agent)

    human_actor = Actor(
        id=user.id,
        type="human",
        name="testuser",
        owner_id=user.id,
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
            ]
        ),
    )
    db.add(human_actor)


    agent_actor = Actor(
        id="agent-1",
        type="agent",
        name="Test Agent",
        owner_id="user-1",
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
            ]
        ),
    )
    db.add(agent_actor)

    repo = Repository(
        id="repo-1",
        owner_id="user-1",
        name="test-repo",
        slug="test-repo",
        description="Test repo",
        visibility="private",
        default_branch="main",
        storage_key="test-repo.git",
    )
    db.add(repo)
    db.flush()

    return user, agent, human_actor, agent_actor, repo


def test_get_changed_files_parser(db):
    user, agent, human_actor, agent_actor, repo = setup_fixtures(db)
    service = ChangeService(db)

    # Mock git outputs for:
    # 1. Added file (src/new.py): +15, -0
    # 2. Modified file (src/main.py): +10, -4
    # 3. Deleted file (src/old.py): +0, -30
    # 4. Binary file (assets/logo.png): - -
    # 5. Renamed file (docs/intro.md -> docs/README.md): +5, -2

    name_status_output = (
        "A\x00src/new.py\x00"
        "M\x00src/main.py\x00"
        "D\x00src/old.py\x00"
        "M\x00assets/logo.png\x00"
        "R100\x00docs/intro.md\x00docs/README.md\x00"
    )

    numstat_output = (
        "15\t0\tsrc/new.py\x00"
        "10\t4\tsrc/main.py\x00"
        "0\t30\tsrc/old.py\x00"
        "-\t-\tassets/logo.png\x00"
        "5\t2\tdocs/README.md\x00"
    )


    def mock_git(repository, *args):
        if "--name-status" in args:
            return name_status_output
        if "--numstat" in args:
            return numstat_output
        return ""

    service._git = mock_git

    files = service.get_changed_files(repo, BASE_COMMIT, RESULTING_COMMIT)

    assert len(files) == 5

    assert files[0] == {
        "operation": "added",
        "path": "src/new.py",
        "old_path": None,
        "additions": 15,
        "deletions": 0,
    }

    assert files[1] == {
        "operation": "modified",
        "path": "src/main.py",
        "old_path": None,
        "additions": 10,
        "deletions": 4,
    }

    assert files[2] == {
        "operation": "deleted",
        "path": "src/old.py",
        "old_path": None,
        "additions": 0,
        "deletions": 30,
    }

    assert files[3] == {
        "operation": "modified",
        "path": "assets/logo.png",
        "old_path": None,
        "additions": 0,
        "deletions": 0,
    }

    assert files[4] == {
        "operation": "renamed",
        "path": "docs/README.md",
        "old_path": "docs/intro.md",
        "additions": 5,
        "deletions": 2,
    }


def test_record_commit_and_api_flow(client, db):
    user, agent, human_actor, agent_actor, repo = setup_fixtures(db)

    # 1. Create a change
    change = Change(
        id="change-test-1",
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Add feature and tests",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status="proposed",
        risk_level="low",
        metadata_json="{}",
    )
    db.add(change)
    db.commit()

    service = ChangeService(db)

    # Mock git operations
    name_status_output = "A\x00test.py\x00M\x00main.py\x00"
    numstat_output = (
        "45\t0\ttest.py\x00"
        "12\t3\tmain.py\x00"
    )


    def mock_git(repository, *args):
        if "--name-status" in args:
            return name_status_output
        if "--numstat" in args:
            return numstat_output
        return ""

    with patch.object(ChangeService, "resolve_commit", return_value=RESULTING_COMMIT), \
         patch.object(ChangeService, "verify_ancestor", return_value=None), \
         patch.object(ChangeService, "_git", side_effect=mock_git), \
         patch("app.services.change_service.ChangePolicyService.evaluate") as mock_policy:
        
        mock_policy.return_value = PolicyDecision(
            decision="allow",
            reason="Low risk",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        )

        service.record_commit(
            change=change,
            repository=repo,
            actor=agent_actor,
            resulting_commit=RESULTING_COMMIT,
        )
        db.commit()


    # Verify ChangeFiles in DB
    files = db.query(ChangeFile).filter(ChangeFile.change_id == change.id).all()
    assert len(files) == 2
    f_map = {f.path: f for f in files}
    assert f_map["test.py"].additions == 45
    assert f_map["test.py"].deletions == 0
    assert f_map["main.py"].additions == 12
    assert f_map["main.py"].deletions == 3

    # Authenticate as user for API testing
    app.dependency_overrides[get_current_user] = lambda: user

    # Test GET /v1/changes/{id}/files
    res_files = client.get(f"/v1/changes/{change.id}/files")
    assert res_files.status_code == 200
    files_json = res_files.json()
    assert len(files_json) == 2
    fj_map = {f["path"]: f for f in files_json}
    assert fj_map["test.py"]["additions"] == 45
    assert fj_map["test.py"]["deletions"] == 0
    assert fj_map["main.py"]["additions"] == 12
    assert fj_map["main.py"]["deletions"] == 3

    # Test GET /v1/changes/{id}
    res_change = client.get(f"/v1/changes/{change.id}")
    assert res_change.status_code == 200
    change_json = res_change.json()
    assert change_json["additions"] == 57
    assert change_json["deletions"] == 3

    # Test GET /v1/changes (list endpoint)
    res_list = client.get(f"/v1/changes?owner={human_actor.name}&repo={repo.slug}")
    assert res_list.status_code == 200
    list_json = res_list.json()
    assert len(list_json) == 1
    assert list_json[0]["additions"] == 57
    assert list_json[0]["deletions"] == 3


def test_agent_and_human_commit_endpoints(client, db):
    user, agent, human_actor, agent_actor, repo = setup_fixtures(db)

    # 1. Test Human Commit Flow
    change_human = Change(
        id="change-human-1",
        repository_id=repo.id,
        actor_id=human_actor.id,
        intent="Human created change",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status="proposed",
        risk_level="low",
        metadata_json="{}",
    )
    db.add(change_human)
    db.commit()

    # 2. Test Agent Commit Flow
    change_agent = Change(
        id="change-agent-1",
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Agent created change",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status="proposed",
        risk_level="low",
        metadata_json="{}",
    )
    db.add(change_agent)
    db.commit()

    name_status_output = "M\x00app.py\x00"
    numstat_output = "8\t2\tapp.py\x00"

    def mock_git(repository, *args):
        if "--name-status" in args:
            return name_status_output
        if "--numstat" in args:
            return numstat_output
        return ""

    with patch.object(ChangeService, "resolve_commit", return_value=RESULTING_COMMIT), \
         patch.object(ChangeService, "verify_ancestor", return_value=None), \
         patch.object(ChangeService, "_git", side_effect=mock_git), \
         patch("app.services.change_service.ChangePolicyService.evaluate") as mock_policy, \
         patch("app.services.authorization_service.AuthorizationService.require", return_value=None):
        
        mock_policy.return_value = PolicyDecision(
            decision="allow",
            reason="Low risk",
            reasons=[],
            conflict_level="none",
            related_change_ids=[],
            dependency_count=0,
            capabilities=[],
        )

        # Human Commit API
        app.dependency_overrides[get_current_user] = lambda: user
        res_human = client.post(
            f"/v1/changes/{change_human.id}/commit",
            json={"resulting_commit": RESULTING_COMMIT},
        )
        assert res_human.status_code == 200
        human_json = res_human.json()
        assert human_json["additions"] == 8
        assert human_json["deletions"] == 2

        # Agent Commit API
        app.dependency_overrides[get_current_agent] = lambda: agent
        res_agent = client.post(
            f"/v1/changes/{change_agent.id}/agent-commit",
            json={"resulting_commit": RESULTING_COMMIT},
        )
        assert res_agent.status_code == 200
        agent_json = res_agent.json()
        assert agent_json["additions"] == 8
        assert agent_json["deletions"] == 2


def test_backward_compatibility_old_records(client, db):
    user, agent, human_actor, agent_actor, repo = setup_fixtures(db)

    # Change created with legacy files (missing additions/deletions or 0)
    change = Change(
        id="change-legacy-1",
        repository_id=repo.id,
        actor_id=human_actor.id,
        intent="Legacy change",
        base_commit=BASE_COMMIT,
        resulting_commit=RESULTING_COMMIT,
        status="recorded",
        risk_level="low",
        metadata_json="{}",
    )
    db.add(change)
    db.flush()

    file1 = ChangeFile(
        change_id=change.id,
        path="legacy.py",
        operation="modified",
        additions=0,
        deletions=0,
    )
    db.add(file1)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user

    res_files = client.get(f"/v1/changes/{change.id}/files")
    assert res_files.status_code == 200
    files_json = res_files.json()
    assert len(files_json) == 1
    assert files_json[0]["additions"] == 0
    assert files_json[0]["deletions"] == 0

    res_change = client.get(f"/v1/changes/{change.id}")
    assert res_change.status_code == 200
    assert res_change.json()["additions"] == 0
    assert res_change.json()["deletions"] == 0

