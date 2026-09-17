from uuid import uuid4
import pytest
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.task import Task
from app.models.user import User
from app.services.governance_service import GovernanceService, GovernanceVerdict
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_repo_with_policies(db, policies: dict):
    user = User(
        id=str(uuid4()),
        username=f"policy_user_{uuid4().hex[:8]}",
        email=f"puser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"test_policy_repo_{uuid4().hex[:8]}",
        description="Repo for testing PR policies",
        visibility="public",
    )
    repo.settings = {"policies": policies}
    db.commit()

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="policy_agent",
        token_prefix="prefix_pol_12",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent)
    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.commit()

    return user, repo, agent, actor


def test_repo_policy_require_task_linkage_enforced_on_pr_creation(db):
    user, repo, agent, actor = setup_repo_with_policies(
        db, {"require_task_linkage": True}
    )
    pr_svc = PullRequestService(db)

    # 1. Create a change with no task
    change_without_task = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Agent change without task",
        risk_level="low",
        resulting_commit="2222222222222222222222222222222222222222",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_without_task)
    db.commit()

    # Attempting to create PR should be blocked by policy
    with pytest.raises(ValueError, match="Policy violation: Pull request must be linked to an active SUTRA Task"):
        pr_svc.create_pull_request(
            repo.id,
            actor.id,
            change_without_task.id,
            "Agent PR without Task",
            "main",
        )

    # 2. Link a task to the change
    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        assigned_agent_id=agent.id,
        title="Valid Task",
        status="in_progress",
        resulting_change_id=change_without_task.id,
    )
    db.add(task)
    db.commit()

    # PR creation now succeeds!
    pr = pr_svc.create_pull_request(
        repo.id,
        actor.id,
        change_without_task.id,
        "Agent PR with Task",
        "main",
    )
    assert pr.status == PullRequest.STATUS_OPEN
    assert pr.repository_id == repo.id


def test_repo_policy_enforce_governed_provenance(db):
    user, repo, agent, actor = setup_repo_with_policies(
        db, {"enforce_governed_provenance": True}
    )
    pr_svc = PullRequestService(db)

    # Create change with unverified external commit
    import json
    unverified_change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Unverified external commit",
        risk_level="low",
        resulting_commit="3333333333333333333333333333333333333333",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
        metadata_json=json.dumps({"commit_origin": "external_unverified"}),
    )
    db.add(unverified_change)
    db.commit()

    with pytest.raises(ValueError, match="Policy violation: Unverified external commits are rejected"):
        pr_svc.create_pull_request(
            repo.id,
            actor.id,
            unverified_change.id,
            "PR with unverified commit",
            "main",
        )


def test_repo_policies_evaluated_in_governance_service(db):
    user, repo, agent, actor = setup_repo_with_policies(
        db,
        {
            "require_task_linkage": True,
            "require_ci_passed": True,
            "min_approvals": 2,
        },
    )
    pr_svc = PullRequestService(db)

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        assigned_agent_id=agent.id,
        title="Gov Task",
        status="in_progress",
    )
    db.add(task)
    db.flush()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Gov change",
        risk_level="low",
        resulting_commit="4444444444444444444444444444444444444444",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    task.resulting_change_id = change.id
    db.add(change)
    db.commit()

    pr = pr_svc.create_pull_request(
        repo.id,
        actor.id,
        change.id,
        "Gov Policy PR",
        "main",
    )

    gov_svc = GovernanceService(db)
    gov = gov_svc.evaluate_pull_request(pr.id)

    # Repository policies are evaluated
    assert "repo_policies" in gov["policy"]
    assert gov["policy"]["repo_policies"]["require_task_linkage"] is True
    assert gov["review"]["required_approvals"] == 2
    # Task linkage passed
    assert any("Linked to SUTRA Task" in p for p in gov["passed"])
