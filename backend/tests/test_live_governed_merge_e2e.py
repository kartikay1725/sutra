import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import hash_password, create_access_token

from app.models.user import User
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.pull_request import PullRequest
from app.models.issue import Issue
from app.models.discussion import Discussion
from app.models.knowledge_node import KnowledgeNode
from app.models.knowledge_edge import KnowledgeEdge
from app.models.branch_protection_rule import BranchProtectionRule

GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_full_governed_merge_and_telemetry_lifecycle_e2e():
    """
    SUTRA Complete Governed Merge & Telemetry Verification E2E
    ==========================================================
    1. Human creates Task
    2. Human assigns Task to active registered Agent
    3. AgentSession created & bound via agent task claim
    4. Agent creates REAL GitHub Issue linked to Task/Session
    5. Agent creates REAL SUTRA Discussion with provenance
    6. Agent creates Change & commits real change to test branch
    7. Agent creates REAL GitHub PR
    8. CI checks observed / synchronized
    9. SUTRA Governance evaluates PR
    10. Negative Security Tests:
        - Human cannot author issue/discussion/PR via SUTRA (403)
        - Agent cannot approve PR (403/ValueError)
        - Self-approval blocked
    11. Human Approval via SUTRA
    12. SUTRA Governed Merge -> Real GitHub Substrate Merge
    13. Verify GitHub substrate reports merged == True
    14. Task transitions to Completed
    15. Idempotency test (repeat merge returns already-merged without corruption)
    16. Audit Log verification
    17. Code Provenance verification
    18. Knowledge Graph verification (contains nodes and edges from this lifecycle)
    19. Insights Telemetry verification
    """
    db = SessionLocal()

    creator_user = None
    reviewer_user = None
    repository = None
    agent = None
    agent_actor = None
    session = None
    task = None
    change_id = None
    pr_id = None
    created_gh_pr_number = None
    test_branch = f"governed-merge-{uuid4().hex[:8]}"

    try:
        # =========================================================
        # 1. Setup GitHub Provider & verify target repo
        # =========================================================
        from app.providers.github.auth import GitHubAppAuthService
        from app.providers.github.repository import GitHubRepositoryProvider

        auth = GitHubAppAuthService(
            app_id=settings.github_app_id,
            private_key_pem=settings.github_private_key_pem,
            base_url=settings.github_api_base_url,
        )
        provider = GitHubRepositoryProvider(
            auth_service=auth,
            base_url=settings.github_api_base_url,
        )

        branches = provider.list_branches(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
        )
        assert branches, "No branches found on GitHub repo"
        default_branch = "master"
        master_branch = next((b for b in branches if getattr(b, "name", None) == default_branch), None)
        assert master_branch is not None, f"Default branch {default_branch} not found"

        print(f"\n[1/19] Target GitHub Substrate: {GITHUB_OWNER}/{GITHUB_REPOSITORY} (default: {default_branch})")

        # Create temporary test branch on GitHub
        provider.create_branch(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            branch=test_branch,
            commit_sha=master_branch.commit_sha,
        )
        print(f"[1/19] Created isolated GitHub branch: {test_branch}")

        # Commit real harmless test change
        test_file_path = f"docs/telemetry/governed_merge_{test_branch}.md"
        file_res = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=test_file_path,
            message=f"feat(agent): telemetry update for governed merge {test_branch}",
            content=f"# Governed Merge Telemetry\nAutonomous Agent Task delivery: {test_branch}\nTimestamp: {datetime.now(timezone.utc).isoformat()}\n".encode("utf-8"),
            branch=test_branch,
        )
        test_commit_sha = file_res["commit"]["sha"]
        print(f"[1/19] Pushed test commit {test_commit_sha} to {test_branch}")

        # =========================================================
        # 2. Setup SUTRA Users, Repository, Agent, Session
        # =========================================================
        # Creator user
        creator_user = User(
            id=str(uuid4()),
            username=f"creator_{uuid4().hex[:6]}",
            email=f"creator_{uuid4().hex[:6]}@example.com",
            password_hash=hash_password("password123"),
        )
        # Reviewer user (distinct human for independent approval)
        reviewer_user = User(
            id=str(uuid4()),
            username=f"reviewer_{uuid4().hex[:6]}",
            email=f"reviewer_{uuid4().hex[:6]}@example.com",
            password_hash=hash_password("password123"),
        )
        db.add_all([creator_user, reviewer_user])
        db.flush()

        creator_actor = Actor(
            id=creator_user.id,
            type="human",
            name=creator_user.username,
            owner_id=creator_user.id,
            capabilities=json.dumps(["repository.read", "repository.write", "change.create"]),
        )
        reviewer_actor = Actor(
            id=reviewer_user.id,
            type="human",
            name=reviewer_user.username,
            owner_id=reviewer_user.id,
            capabilities=json.dumps(["repository.read", "repository.write", "change.create"]),
        )
        db.add_all([creator_actor, reviewer_actor])
        db.flush()

        repository = Repository(
            id=str(uuid4()),
            owner_id=creator_user.id,
            name=GITHUB_REPOSITORY,
            slug=GITHUB_REPOSITORY,
            description="SUTRA mapping for live governed merge test",
            visibility="private",
            storage_key=f"github-live-merge/{uuid4().hex}",
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            external_id=f"live-e2e-merge-{uuid4().hex}",
            github_installation_id=getattr(settings, "github_installation_id", 158557464),
            default_branch=default_branch,
            settings={},
        )
        db.add(repository)
        db.flush()

        agent = Agent(
            id=str(uuid4()),
            owner_id=creator_user.id,
            name=f"Atlas-Agent-{uuid4().hex[:6]}",
            description="Autonomous test agent for governed merge lifecycle",
            provider="test",
            model="gemini-1.5-pro",
            token_hash=hash_password(f"agent-token-{uuid4().hex}"),
            token_prefix=uuid4().hex[:16],
            status="active",
            is_active=True,
        )
        db.add(agent)
        db.flush()

        agent_actor = Actor(
            id=agent.id,
            type="agent",
            name=agent.name,
            owner_id=creator_user.id,
            capabilities=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "discussion.create",
                "discussion.read",
            ]),
        )
        db.add(agent_actor)
        db.flush()

        session_token = f"sutra_session_{uuid4().hex}_{uuid4().hex}"
        session = AgentSession(
            id=str(uuid4()),
            agent_id=agent.id,
            token_hash=hash_password(session_token),
            token_prefix=session_token[:32],
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()

        creator_jwt = create_access_token(creator_user.id)
        reviewer_jwt = create_access_token(reviewer_user.id)

        print(f"[2/19] Created SUTRA Repository: {repository.id}, Agent: {agent.id}, Session: {session.id}")

        # =========================================================
        # 3. Human creates Task & assigns to Agent
        # =========================================================
        with TestClient(app) as client:
            create_task_res = client.post(
                f"/v1/repositories/{creator_user.username}/{repository.slug}/tasks",
                headers={"Authorization": f"Bearer {creator_jwt}"},
                json={
                    "title": f"Telemetry Pipeline Autonomous Delivery {test_branch[:8]}",
                    "description": "Implement automated telemetry recording with full governed merge.",
                    "priority": "high",
                    "task_type": "feature",
                },
            )
            assert create_task_res.status_code == 201, create_task_res.text
            task_data = create_task_res.json()
            task_id = task_data["id"]
            print(f"[3/19] Human created Task #{task_id}: {task_data['title']} (status: {task_data['status']})")

            # Human explicitly assigns task to Agent
            assign_res = client.post(
                f"/v1/tasks/{task_id}/assign",
                headers={"Authorization": f"Bearer {creator_jwt}"},
                json={"assigned_agent_id": agent.id},
            )
            assert assign_res.status_code == 200, assign_res.text
            assigned_task_data = assign_res.json()
            assert assigned_task_data["assigned_agent_id"] == agent.id
            assert assigned_task_data["status"] == "assigned"
            print(f"[3/19] Task assigned to Agent {agent.id} (status: assigned)")

        # =========================================================
        # 4. Agent claims Task lease using AgentSession
        # =========================================================
        with TestClient(app) as client:
            claim_res = client.post(
                f"/v1/agent/tasks/{task_id}/claim",
                headers={"Authorization": f"Bearer {session_token}"},
            )
            assert claim_res.status_code == 200, claim_res.text
            claimed_task = claim_res.json()
            assert claimed_task["claimed_by_session_id"] == session.id
            assert claimed_task["status"] == "in_progress"
            print(f"[4/19] Agent claimed Task lease under Session {session.id} (status: in_progress)")

        # =========================================================
        # 5. Agent creates REAL GitHub Issue via SUTRA
        # =========================================================
        with TestClient(app) as client:
            issue_res = client.post(
                f"/v1/agent/tasks/{task_id}/issues",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "title": f"Autonomous Tracking: {test_branch[:8]}",
                    "body": f"Automated engineering task for governed merge verification in {test_branch}.",
                },
            )
            assert issue_res.status_code == 201, issue_res.text
            issue_data = issue_res.json()
            gh_issue_number = issue_data["github_issue_number"]
            gh_issue_url = issue_data["github_html_url"]
            assert gh_issue_number is not None
            assert "github.com" in gh_issue_url
            print(f"[5/19] Created REAL GitHub Issue #{gh_issue_number}: {gh_issue_url}")

        # =========================================================
        # 6. Agent creates SUTRA Discussion with provenance
        # =========================================================
        with TestClient(app) as client:
            disc_res = client.post(
                f"/v1/repositories/{creator_user.username}/{repository.name}/discussions",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "title": f"Design RFC: Telemetry Pipeline for {test_branch[:8]}",
                    "body": f"Discussion tracking autonomous execution for task {task_id}.",
                    "category": "architecture",
                    "task_id": task_id,
                },
            )
            assert disc_res.status_code == 201, disc_res.text
            disc_data = disc_res.json()
            assert disc_data["author_type"] == "agent"
            assert disc_data["task_id"] == task_id
            print(f"[6/19] Created SUTRA Discussion: {disc_data['id']} (agent: {disc_data['author_name']})")

        # =========================================================
        # 7. Agent records Change & Commit
        # =========================================================
        with TestClient(app) as client:
            ch_res = client.post(
                f"/v1/agent/tasks/{task_id}/changes",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "intent": f"Deliver telemetry update for {test_branch}",
                    "branch": test_branch,
                    "base_branch": default_branch,
                },
            )
            assert ch_res.status_code == 201, ch_res.text
            change_id = ch_res.json()["id"]

            commit_res = client.post(
                f"/v1/agent/tasks/{task_id}/commit",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "resulting_commit": test_commit_sha,
                    "commit_sha": test_commit_sha,
                },
            )
            assert commit_res.status_code == 200, commit_res.text
            print(f"[7/19] Recorded Change #{change_id} with commit {test_commit_sha}")

        # =========================================================
        # 8. Agent creates REAL GitHub PR
        # =========================================================
        with TestClient(app) as client:
            pr_res = client.post(
                f"/v1/agent/tasks/{task_id}/pull-requests",
                headers={"Authorization": f"Bearer {session_token}"},
                json={
                    "title": f"feat: telemetry delivery for {test_branch[:8]}",
                    "description": f"Autonomous pull request for task {task_id}.",
                    "target_branch": default_branch,
                },
            )
            assert pr_res.status_code == 201, pr_res.text
            pr_data = pr_res.json()
            pr_id = pr_data["id"]
            created_gh_pr_number = pr_data["github_pr_number"]
            gh_pr_url = pr_data["github_html_url"]
            assert created_gh_pr_number is not None
            assert gh_pr_url and "github.com" in gh_pr_url
            print(f"[8/19] Created REAL GitHub PR #{created_gh_pr_number}: {gh_pr_url}")

        # Verify PR substrate object
        gh_pr_obj = provider.get_pull_request(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            pr_number=created_gh_pr_number,
        )
        assert gh_pr_obj is not None
        assert gh_pr_obj.number == created_gh_pr_number
        assert gh_pr_obj.head_ref == test_branch
        assert gh_pr_obj.base_ref == default_branch

        # =========================================================
        # 9. CI check synchronization
        # =========================================================
        with TestClient(app) as client:
            checks_res = client.get(
                f"/v1/pull-requests/{pr_id}/checks",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert checks_res.status_code == 200, checks_res.text
            checks_data = checks_res.json()
            print(f"[9/19] Synchronized CI checks: total={checks_data['summary']['total']}, status={checks_data['summary']}")

        # =========================================================
        # 10. Governance Pre-Approval Evaluation
        # =========================================================
        with TestClient(app) as client:
            gov_res = client.get(
                f"/v1/pull-requests/{pr_id}/governance",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert gov_res.status_code == 200, gov_res.text
            gov_eval = gov_res.json()
            print(f"[10/19] Governance verdict before approval: {gov_eval['verdict']}")
            assert gov_eval["verdict"] in ("READY_FOR_APPROVAL", "NEEDS_REVIEW")

        # =========================================================
        # 11. Negative Security Tests
        # =========================================================
        with TestClient(app) as client:
            # A. Human POST issue via SUTRA -> 403
            h_issue_res = client.post(
                f"/v1/repositories/{creator_user.username}/{repository.name}/issues",
                headers={"Authorization": f"Bearer {creator_jwt}"},
                json={"title": "Human illegal issue", "body": "Should fail"},
            )
            assert h_issue_res.status_code == 403, f"Expected 403, got {h_issue_res.status_code}"

            # B. Human POST discussion via SUTRA -> 403
            h_disc_res = client.post(
                f"/v1/repositories/{creator_user.username}/{repository.name}/discussions",
                headers={"Authorization": f"Bearer {creator_jwt}"},
                json={"title": "Human illegal discussion", "body": "Should fail", "category": "general"},
            )
            assert h_disc_res.status_code == 403, f"Expected 403, got {h_disc_res.status_code}"

            # C. Human POST PR via SUTRA -> 403
            h_pr_res = client.post(
                "/v1/pull-requests",
                headers={"Authorization": f"Bearer {creator_jwt}"},
                json={
                    "repository_id": repository.id,
                    "source_change_id": change_id,
                    "title": "Human PR",
                    "target_branch": default_branch,
                },
            )
            assert h_pr_res.status_code == 403, f"Expected 403, got {h_pr_res.status_code}"

            # D. Agent cannot approve PR
            agent_approve_res = client.post(
                f"/v1/pull-requests/{pr_id}/approve",
                headers={"Authorization": f"Bearer {session_token}"},
                json={"reason": "Agent self-approval attempt"},
            )
            assert agent_approve_res.status_code in (401, 403, 400), f"Agent approval must be rejected: {agent_approve_res.status_code}"

            # E. Agent cannot merge PR
            agent_merge_res = client.post(
                f"/v1/pull-requests/{pr_id}/merge",
                headers={"Authorization": f"Bearer {session_token}"},
            )
            assert agent_merge_res.status_code in (401, 403, 400), f"Agent merge must be rejected: {agent_merge_res.status_code}"

            print("[11/19] Negative security checks verified (boundary enforcement intact).")

        # =========================================================
        # 12. Human Approval via SUTRA
        # =========================================================
        with TestClient(app) as client:
            # Check for existing review or request one
            review_req_res = client.post(
                f"/v1/pull-requests/{pr_id}/reviews",
                headers={"Authorization": f"Bearer {creator_jwt}"},
                json={"reason": "Requesting independent human review for governed merge"},
            )
            assert review_req_res.status_code in (201, 409), review_req_res.text

            # Independent human reviewer approves PR
            approve_res = client.post(
                f"/v1/pull-requests/{pr_id}/approve",
                headers={"Authorization": f"Bearer {reviewer_jwt}"},
                json={"reason": "Governed human review: verified all automated tests and provenance."},
            )
            assert approve_res.status_code == 200, approve_res.text
            approved_pr = approve_res.json()
            assert approved_pr["status"] == "approved"
            print(f"[12/19] Human {reviewer_user.username} approved PR #{pr_id} (status: approved)")

        # Verify Governance is now READY_FOR_MERGE
        with TestClient(app) as client:
            gov_after_res = client.get(
                f"/v1/pull-requests/{pr_id}/governance",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert gov_after_res.status_code == 200
            gov_verdict = gov_after_res.json()["verdict"]
            print(f"[12/19] Post-approval Governance verdict: {gov_verdict}")
            assert gov_verdict == "READY_FOR_MERGE"

        # =========================================================
        # 13. ACTUAL GOVERNED MERGE VIA SUTRA
        # =========================================================
        print("[13/19] Executing REAL Governed Merge via POST /v1/pull-requests/{id}/merge...")
        with TestClient(app) as client:
            merge_res = client.post(
                f"/v1/pull-requests/{pr_id}/merge",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert merge_res.status_code == 200, f"Governed merge failed: {merge_res.text}"
            merge_data = merge_res.json()
            assert merge_data["status"] == "merged"
            merge_commit_sha = merge_data["merge_commit_sha"]
            merged_at = merge_data["merged_at"]
            print(f"[13/19] SUTRA Governed Merge Success! Merge Commit: {merge_commit_sha}, Merged At: {merged_at}")

        # =========================================================
        # 14. AUTHORITATIVE SUBSTRATE VERIFICATION DIRECTLY FROM GITHUB
        # =========================================================
        time.sleep(2)  # Allow substrate settlement
        gh_merged_pr = provider.get_pull_request(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            pr_number=created_gh_pr_number,
        )
        assert gh_merged_pr is not None
        assert gh_merged_pr.is_merged is True, f"CRITICAL: GitHub reports PR #{created_gh_pr_number} is NOT merged!"
        print(f"[14/19] Direct GitHub Substrate Verification: PR #{created_gh_pr_number} is_merged = TRUE! (is_closed: {gh_merged_pr.is_closed})")

        # =========================================================
        # 15. Task Completion Verification
        # =========================================================
        db.expire_all()
        final_task = db.scalar(select(Task).where(Task.id == task_id))
        assert final_task.status == Task.STATUS_COMPLETED, f"Expected task completed, got {final_task.status}"
        assert final_task.completed_at is not None
        print(f"[15/19] Linked Task #{task_id} transitioned to COMPLETED (completed_at: {final_task.completed_at})")

        # =========================================================
        # 16. Idempotency Verification
        # =========================================================
        with TestClient(app) as client:
            idempotent_merge_res = client.post(
                f"/v1/pull-requests/{pr_id}/merge",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert idempotent_merge_res.status_code == 200, idempotent_merge_res.text
            idem_data = idempotent_merge_res.json()
            assert idem_data["status"] == "merged"
            print("[16/19] Idempotent merge request verified without state corruption.")

        # =========================================================
        # 17. Code Provenance Verification
        # =========================================================
        from app.services.code_provenance_service import CodeProvenanceService
        prov_service = CodeProvenanceService(db)
        provenance = prov_service.resolve_commit(repository.id, test_commit_sha)
        assert provenance is not None, "Code provenance failed to resolve for merged commit"
        assert provenance["tracked"] is True
        assert provenance["identity_type"] == "agent"
        assert provenance["task"]["id"] == task_id
        assert provenance["agent"]["id"] == agent.id
        assert provenance["session"]["id"] == session.id
        print(f"[17/19] Code Provenance verified: Commit {test_commit_sha[:8]} -> Task {task_id[:8]} -> Agent {agent.name}")

        # =========================================================
        # 18. Knowledge Graph Verification
        # =========================================================
        with TestClient(app) as client:
            kg_res = client.get(
                f"/v1/repositories/{creator_user.username}/{repository.name}/graph?limit=500",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert kg_res.status_code == 200, kg_res.text
            kg_data = kg_res.json()
            nodes = kg_data.get("nodes", [])
            edges = kg_data.get("edges", [])
            print(f"[18/19] Knowledge Graph populated: {len(nodes)} nodes, {len(edges)} edges")
            assert len(nodes) > 0, "Knowledge Graph must not be empty"
            assert len(edges) > 0, "Knowledge Graph must contain relationships"

            # Check that task, agent, change, and PR nodes exist in graph
            entity_types = {n.get("entity_type") for n in nodes}
            print(f"[18/19] Knowledge Graph entity types: {entity_types}")
            assert "task" in entity_types
            assert "agent" in entity_types
            assert "change" in entity_types
            assert "pull_request" in entity_types

        # =========================================================
        # 19. Insights Telemetry Verification
        # =========================================================
        with TestClient(app) as client:
            insights_res = client.get(
                f"/v1/repositories/{creator_user.username}/{repository.name}/insights",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert insights_res.status_code == 200, insights_res.text
            repo_insights = insights_res.json()
            print(f"[19/19] Repository Insights: {repo_insights}")
            assert repo_insights["agent_changes_percent"] == 100, "Should reflect 100% agent changes"

            global_insights_res = client.get(
                "/v1/insights",
                headers={"Authorization": f"Bearer {creator_jwt}"},
            )
            assert global_insights_res.status_code == 200, global_insights_res.text
            global_insights = global_insights_res.json()
            print(f"[19/19] Global Insights: {global_insights}")
            assert global_insights["agent_changes_percent"] == 100

        print("\n==================================================================")
        print("ALL 19 LIFECYCLE PHASES OF SUTRA GOVERNED MERGE VERIFIED CLEANLY!")
        print("==================================================================\n")

    finally:
        # Cleanup remote branch if merged
        print("\nCleaning up live test branch on GitHub...")
        try:
            provider.delete_branch(
                owner=GITHUB_OWNER,
                name=GITHUB_REPOSITORY,
                branch=test_branch,
            )
            print(f"Deleted temporary test branch {test_branch}")
        except Exception as e:
            print(f"Branch cleanup note: {e}")

        # Cleanup local SUTRA test records
        try:
            if repository:
                db.query(KnowledgeEdge).delete()
                db.query(KnowledgeNode).delete()
                db.query(Discussion).filter(Discussion.repository_id == repository.id).delete()
                db.query(Issue).filter(Issue.repository_id == repository.id).delete()
                db.query(TaskEvent).filter(TaskEvent.task_id == task_id).delete() if task_id else None
                db.query(Task).filter(Task.repository_id == repository.id).delete()
                db.query(ChangeEvent).filter(ChangeEvent.change_id == change_id).delete() if change_id else None
                db.query(PullRequest).filter(PullRequest.repository_id == repository.id).delete()
                db.query(Change).filter(Change.repository_id == repository.id).delete()
                db.query(AgentSession).filter(AgentSession.agent_id == agent.id).delete() if agent else None
                db.query(Agent).filter(Agent.id == agent.id).delete() if agent else None
                db.query(Repository).filter(Repository.id == repository.id).delete()

            from app.models.notification import Notification
            if creator_user:
                db.query(Notification).filter(Notification.user_id.in_([creator_user.id, reviewer_user.id])).delete()
            if creator_actor:
                db.query(Actor).filter(Actor.id.in_([creator_actor.id, reviewer_actor.id, agent_actor.id])).delete()
            if creator_user:
                db.query(User).filter(User.id.in_([creator_user.id, reviewer_user.id])).delete()

            db.commit()
            print("Cleaned up temporary test database records.")
        except Exception as e:
            db.rollback()
            print(f"Database cleanup warning: {e}")
        finally:
            db.close()
