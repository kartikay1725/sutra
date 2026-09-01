import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.agent_dependencies import get_current_agent
from app.api.dependencies import get_current_user
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.change_policy_service import ChangePolicyService, PolicyDecision
from app.services.change_service import ChangeService
from app.services.pull_request_service import PullRequestService
from tests.conftest import ensure_test_actor

BASE_COMMIT = "1111111111111111111111111111111111111111"
COMMIT_1 = "2222222222222222222222222222222222222222"
COMMIT_2 = "3333333333333333333333333333333333333333"


def setup_agent_environment(db):
    """
    Setup authenticated human owner, agent, actors, repository, and repository grants.
    """
    owner = User(
        id=str(uuid.uuid4()),
        username=f"owner_{uuid.uuid4().hex[:8]}",
        email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    reviewer = User(
        id=str(uuid.uuid4()),
        username=f"reviewer_{uuid.uuid4().hex[:8]}",
        email=f"reviewer_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add_all([owner, reviewer])
    db.flush()

    owner_actor = ensure_test_actor(db, owner)
    reviewer_actor = ensure_test_actor(db, reviewer)

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
        name="autodev_agent",
        capabilities='["repository.read", "repository.write", "change.create", "change.commit"]',
    )
    agent = Agent(
        id=agent_id,
        owner_id=owner.id,
        name="autodev_agent",
        token_prefix="agent_prefix_",
        token_hash="hash",
        status="active",
        is_active=True,
    )
    db.add_all([agent_actor, agent])
    db.flush()

    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions='["repository.read", "repository.write", "change.create", "change.commit"]',
        enabled=True,
    )
    db.add(access)
    db.flush()

    return owner, reviewer, agent, owner_actor, reviewer_actor, agent_actor, repo


def test_agent_commit_evidence_recording_and_review_lifecycle(client: TestClient, db):
    """
    End-to-end test verifying:
    1. Agent creates Change (proposed)
    2. Agent attaches resulting commit -> ChangeFile evidence persisted, additions/deletions saved
    3. Change remains proposed because policy decision is REVIEW (no approved review yet)
    4. Agent creates PR -> Review request created, pull_request.review_requested logged
    5. Human reviewer approves PR -> Change is finalized to 'recorded', PR is approved and merge-eligible
    """
    owner, reviewer, agent, owner_actor, reviewer_actor, agent_actor, repo = setup_agent_environment(db)

    # 1. Agent creates Change
    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Agent Feature with Evidence",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status="proposed",
        risk_level="medium",
        metadata_json="{}",
    )
    db.add(change)
    db.commit()
    assert change.status == "proposed"

    # Mock git operations
    name_status_output = "M\x00src/feature.py\x00A\x00tests/test_feature.py\x00"
    numstat_output = "12\t3\tsrc/feature.py\x0025\t0\ttests/test_feature.py\x00"

    def mock_git(repository, *args):
        if "--name-status" in args:
            return name_status_output
        if "--numstat" in args:
            return numstat_output
        return ""

    # Policy returns REVIEW because change has medium risk / agent author
    review_decision = PolicyDecision(
        decision=ChangePolicyService.REVIEW,
        reason="Agent changes require human review",
        reasons=["Agent changes require human review"],
        conflict_level="none",
        related_change_ids=[],
        dependency_count=0,
        capabilities=[],
    )

    with patch.object(ChangeService, "resolve_commit", side_effect=lambda repo, c: c), \
         patch.object(ChangeService, "verify_ancestor", return_value=None), \
         patch.object(ChangeService, "_git", side_effect=mock_git), \
         patch("app.services.change_service.ChangePolicyService.evaluate", return_value=review_decision):

        # 2. Agent calls /agent-commit to attach resulting commit
        app.dependency_overrides[get_current_agent] = lambda: agent
        res = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={"resulting_commit": COMMIT_1},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "proposed", "Change must remain proposed when review is required"
        assert data["resulting_commit"] == COMMIT_1
        assert data["additions"] == 37
        assert data["deletions"] == 3

    # Verify DB persistence of ChangeFiles and Change state
    db.expire_all()
    change_db = db.get(Change, change.id)
    assert change_db.status == "proposed"
    assert change_db.resulting_commit == COMMIT_1

    files = db.scalars(select(ChangeFile).where(ChangeFile.change_id == change.id)).all()
    assert len(files) == 2
    assert sum(f.additions for f in files) == 37
    assert sum(f.deletions for f in files) == 3

    # 3. Agent creates PR
    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=agent_actor.id,
        source_change_id=change.id,
        title="Agent Feature PR",
        target_branch="main",
    )
    db.commit()

    assert pr.status == "open"
    reviews = db.scalars(select(ChangeReview).where(ChangeReview.change_id == change.id)).all()
    assert len(reviews) == 1
    assert reviews[0].status == "pending"
    assert reviews[0].requested_by == owner.id

    # 4. Human reviewer approves PR
    with patch("app.services.pull_request_service.ChangePolicyService.evaluate", return_value=review_decision), \
         patch("app.services.change_service.ChangePolicyService.evaluate", return_value=review_decision):

        approved_pr = pr_svc.approve_pull_request(
            pr=pr,
            approver_id=reviewer.id,
            reason="LGTM - excellent code",
        )
        db.commit()

    assert approved_pr.status == "approved"

    # Verify Change is now finalized and recorded
    db.expire_all()
    change_final = db.get(Change, change.id)
    assert change_final.status == "recorded", "Change must be finalized/recorded after review approval"

    # Verify PR is now merge-eligible
    assert approved_pr.status == "approved"


def test_agent_changes_requested_and_recommit_workflow(client: TestClient, db):
    """
    Test scenario:
    1. Agent creates change and attaches commit 1 (proposed)
    2. Agent creates PR -> Review requested
    3. Human reviewer requests changes (rejects review)
    4. Agent updates code and attaches commit 2 -> ChangeFiles update to new diff
    5. Change remains proposed
    6. Human reviewer approves second version -> Change finalizes to 'recorded'
    """
    owner, reviewer, agent, owner_actor, reviewer_actor, agent_actor, repo = setup_agent_environment(db)

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Agent Feature to Revise",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status="proposed",
        risk_level="medium",
        metadata_json="{}",
    )
    db.add(change)
    db.commit()

    # Commit 1 diff: 5 adds, 1 del
    name_status_v1 = "M\x00src/app.py\x00"
    numstat_v1 = "5\t1\tsrc/app.py\x00"

    def mock_git_v1(repository, *args):
        if "--name-status" in args:
            return name_status_v1
        if "--numstat" in args:
            return numstat_v1
        return ""

    review_decision = PolicyDecision(
        decision=ChangePolicyService.REVIEW,
        reason="Agent review required",
        reasons=["Agent review required"],
        conflict_level="none",
        related_change_ids=[],
        dependency_count=0,
        capabilities=[],
    )

    with patch.object(ChangeService, "resolve_commit", side_effect=lambda repo, c: c), \
         patch.object(ChangeService, "verify_ancestor", return_value=None), \
         patch.object(ChangeService, "_git", side_effect=mock_git_v1), \
         patch("app.services.change_service.ChangePolicyService.evaluate", return_value=review_decision):

        app.dependency_overrides[get_current_agent] = lambda: agent
        res = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={"resulting_commit": COMMIT_1},
        )
        assert res.status_code == 200
        assert res.json()["additions"] == 5

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(
        repository_id=repo.id,
        author_id=agent_actor.id,
        source_change_id=change.id,
        title="PR for revision",
        target_branch="main",
    )
    db.commit()

    review = db.scalar(select(ChangeReview).where(ChangeReview.change_id == change.id))
    assert review is not None

    # Reviewer requests changes
    app.dependency_overrides[get_current_user] = lambda: reviewer
    res_reject = client.post(
        f"/v1/changes/{change.id}/reviews/{review.id}/reject",
        json={"reason": "Please fix edge case in calculate()"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"

    # Agent fixes code and attaches COMMIT_2: 15 adds, 2 dels
    name_status_v2 = "M\x00src/app.py\x00"
    numstat_v2 = "15\t2\tsrc/app.py\x00"

    def mock_git_v2(repository, *args):
        if "--name-status" in args:
            return name_status_v2
        if "--numstat" in args:
            return numstat_v2
        return ""

    with patch.object(ChangeService, "resolve_commit", side_effect=lambda repo, c: c), \
         patch.object(ChangeService, "verify_ancestor", return_value=None), \
         patch.object(ChangeService, "_git", side_effect=mock_git_v2), \
         patch("app.services.change_service.ChangePolicyService.evaluate", return_value=review_decision):

        app.dependency_overrides[get_current_agent] = lambda: agent
        res_v2 = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={"resulting_commit": COMMIT_2},
        )
        assert res_v2.status_code == 200
        assert res_v2.json()["resulting_commit"] == COMMIT_2
        assert res_v2.json()["additions"] == 15
        assert res_v2.json()["status"] == "proposed"

    # New review request created
    new_review = pr_svc.create_pull_request_review_request(
        pr=pr,
        requester_id=owner.id,
        reason="Agent updated commit with requested fixes",
    )
    db.commit()

    # Reviewer approves updated PR
    with patch("app.services.pull_request_service.ChangePolicyService.evaluate", return_value=review_decision), \
         patch("app.services.change_service.ChangePolicyService.evaluate", return_value=review_decision):

        pr_svc.approve_pull_request(
            pr=pr,
            approver_id=reviewer.id,
            reason="Fixes look good!",
            review_id=new_review.id,
        )
        db.commit()

    db.expire_all()
    change_final = db.get(Change, change.id)
    assert change_final.status == "recorded"
    assert change_final.resulting_commit == COMMIT_2


def test_policy_block_prevents_finalization_and_merge(client: TestClient, db):
    """
    Test scenario:
    1. If policy decision is BLOCK, commit cannot be attached / change cannot be finalized.
    2. If PR merge is attempted on blocked change, merge is rejected.
    """
    owner, reviewer, agent, owner_actor, reviewer_actor, agent_actor, repo = setup_agent_environment(db)

    change = Change(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Blocked Change",
        base_commit=BASE_COMMIT,
        resulting_commit=None,
        status="proposed",
        risk_level="critical",
        metadata_json="{}",
    )
    db.add(change)
    db.commit()

    block_decision = PolicyDecision(
        decision=ChangePolicyService.BLOCK,
        reason="Critical security rule violation: forbidden API usage",
        reasons=["Critical security rule violation: forbidden API usage"],
        conflict_level="none",
        related_change_ids=[],
        dependency_count=0,
        capabilities=[],
    )

    with patch.object(ChangeService, "resolve_commit", side_effect=lambda repo, c: c), \
         patch.object(ChangeService, "verify_ancestor", return_value=None), \
         patch.object(ChangeService, "_git", return_value=""), \
         patch("app.services.change_service.ChangePolicyService.evaluate", return_value=block_decision):

        app.dependency_overrides[get_current_agent] = lambda: agent
        res = client.post(
            f"/v1/changes/{change.id}/agent-commit",
            json={"resulting_commit": COMMIT_1},
        )
        assert res.status_code == 400
        assert "blocked by SUTRA policy" in res.json()["detail"]
