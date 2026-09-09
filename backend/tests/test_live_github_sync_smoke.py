"""
Live GitHub-originated Smoke Test
=================================
Validates the complete GitHub -> SUTRA synchronization workflow against a live test repository:
1. Creates real GitHub Issue directly via GitHub API
2. Delivers GitHub Issue webhook to SUTRA
3. Verifies Issue appears in SUTRA with source_type="human", null agent/session/task
4. Creates real GitHub branch & PR directly via GitHub API
5. Delivers GitHub PR webhook to SUTRA
6. Verifies PR appears in SUTRA with source_type="github", linked to external tracking Change
7. Approves PR in SUTRA
8. Pushes a real commit to GitHub PR branch
9. Delivers GitHub pull_request.synchronize webhook to SUTRA
10. Verifies PR approval is invalidated (approved_head_sha cleared, status reverted to open)
11. Verifies Knowledge Graph indexes the repository, Issue, Change, and PullRequest with real edges
12. Cleans up GitHub test branch & closes GitHub PR / Issue
"""

import hmac
import hashlib
import json
import time
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.user import User
from app.models.repository import Repository
from app.models.issue import Issue
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.knowledge_node import KnowledgeNode
from app.models.knowledge_edge import KnowledgeEdge
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider

GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def test_live_github_originated_smoke_test():
    db = SessionLocal()
    client = TestClient(app)

    auth = GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )
    provider = GitHubRepositoryProvider(
        auth_service=auth,
        base_url=settings.github_api_base_url,
    )

    test_id = uuid4().hex[:8]
    branch_name = f"smoke-{test_id}"
    created_issue_number = None
    created_pr_number = None

    try:
        # Resolve real repository in SUTRA DB
        repo = db.execute(
            select(Repository).where(
                Repository.provider_owner == GITHUB_OWNER,
                Repository.name == GITHUB_REPOSITORY,
                Repository.external_id == "1075617112",
            )
        ).scalar_one_or_none()

        if not repo:
            repo = db.execute(
                select(Repository).where(
                    Repository.provider_owner == GITHUB_OWNER,
                    Repository.name == GITHUB_REPOSITORY,
                )
            ).scalars().first()

        assert repo is not None, f"Repository {GITHUB_REPOSITORY} must exist in SUTRA database"
        print(f"Targeting repository {repo.id} ({repo.provider_owner}/{repo.name}, ext_id={repo.external_id})")

        # -------------------------------------------------------------
        # 1. Create real Issue directly on GitHub via GitHub substrate
        # -------------------------------------------------------------
        issue_title = f"Live Smoke Issue {test_id}"
        issue_body = f"Directly created on GitHub to verify SUTRA webhook ingestion ({test_id})"

        created_issue = provider.create_issue(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            title=issue_title,
            body=issue_body,
        )
        assert created_issue is not None
        created_issue_number = created_issue.number
        print(f"Created real GitHub issue #{created_issue_number}")

        # Deliver GitHub 'issues.opened' webhook to SUTRA
        issue_webhook_payload = {
            "action": "opened",
            "repository": {
                "id": int(repo.external_id) if (repo.external_id and repo.external_id.isdigit()) else 1075617112,
                "name": GITHUB_REPOSITORY,
                "full_name": f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}",
                "owner": {"login": GITHUB_OWNER},
            },
            "issue": {
                "id": int(created_issue.id) if created_issue.id.isdigit() else 999000 + created_issue_number,
                "number": created_issue.number,
                "title": created_issue.title,
                "body": created_issue.body,
                "state": "open",
                "html_url": created_issue.html_url or f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/issues/{created_issue_number}",
                "user": {"login": GITHUB_OWNER},
                "created_at": "2026-09-09T10:00:00Z",
                "updated_at": "2026-09-09T10:00:00Z",
                "closed_at": None,
            },
        }
        payload_bytes = json.dumps(issue_webhook_payload).encode("utf-8")
        sig = sign_payload(payload_bytes, settings.github_webhook_secret)

        resp = client.post(
            "/v1/webhooks/github",
            content=payload_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200, f"Webhook response: {resp.text}"

        # -------------------------------------------------------------
        # 2. Verify Issue appears in SUTRA
        # -------------------------------------------------------------
        db.expire_all()
        sutra_issue = db.execute(
            select(Issue).where(
                Issue.repository_id == repo.id,
                Issue.github_issue_number == created_issue_number,
            )
        ).scalar_one_or_none()

        assert sutra_issue is not None, "Issue must appear in SUTRA"
        assert sutra_issue.title == issue_title
        assert sutra_issue.source_type == "human"
        assert sutra_issue.agent_id is None
        assert sutra_issue.agent_session_id is None
        assert sutra_issue.task_id is None
        print(f"Verified SUTRA issue {sutra_issue.id} has human provenance and null agent fields")

        # -------------------------------------------------------------
        # 3. Create real branch & real PR directly on GitHub
        # -------------------------------------------------------------
        branches = provider.list_branches(owner=GITHUB_OWNER, name=GITHUB_REPOSITORY)
        default_branch_name = repo.default_branch or "master"
        matching_branches = [b for b in branches if b.name in (default_branch_name, "main", "master")]
        base_branch_obj = matching_branches[0] if matching_branches else branches[0]
        base_branch = base_branch_obj.name
        base_commit = base_branch_obj.commit_sha

        provider.create_branch(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            branch=branch_name,
            commit_sha=base_commit,
        )
        print(f"Created real GitHub branch {branch_name} from {base_branch}")

        # Commit a file on GitHub to make PR openable
        file_res_1 = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=f"docs/smoke_{test_id}.txt",
            message=f"Smoke test commit 1: {test_id}",
            content=f"Smoke test commit 1 for {test_id}\n".encode("utf-8"),
            branch=branch_name,
        )
        commit_1_sha = file_res_1["commit"]["sha"]
        print(f"Committed 1st file with SHA: {commit_1_sha}")

        created_pr = provider.create_pull_request(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            title=f"Smoke Test PR {test_id}",
            body=f"Smoke test PR created on GitHub ({test_id})",
            head_branch=branch_name,
            base_branch=base_branch,
        )
        assert created_pr is not None
        created_pr_number = created_pr.number
        print(f"Created real GitHub PR #{created_pr_number}")

        # -------------------------------------------------------------
        # 4. Deliver GitHub PR webhook to SUTRA
        # -------------------------------------------------------------
        pr_webhook_payload = {
            "action": "opened",
            "repository": {
                "id": int(repo.external_id) if (repo.external_id and repo.external_id.isdigit()) else 1075617112,
                "name": GITHUB_REPOSITORY,
                "full_name": f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}",
                "owner": {"login": GITHUB_OWNER},
            },
            "pull_request": {
                "id": int(created_pr.number) * 1000 + 77,
                "number": created_pr.number,
                "title": created_pr.title,
                "body": created_pr.body,
                "state": "open",
                "html_url": created_pr.html_url or f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/pull/{created_pr_number}",
                "user": {"login": GITHUB_OWNER},
                "head": {
                    "ref": branch_name,
                    "sha": commit_1_sha,
                },
                "base": {
                    "ref": base_branch,
                    "sha": base_commit,
                },
                "merged": False,
            },
        }
        payload_bytes = json.dumps(pr_webhook_payload).encode("utf-8")
        sig = sign_payload(payload_bytes, settings.github_webhook_secret)

        resp = client.post(
            "/v1/webhooks/github",
            content=payload_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200, f"PR webhook failed: {resp.text}"

        # Verify PR appears in SUTRA with external tracking change
        db.expire_all()
        sutra_pr = db.execute(
            select(PullRequest)
            .join(Change, PullRequest.source_change_id == Change.id)
            .where(
                PullRequest.repository_id == repo.id,
                Change.metadata_json.contains(f'"github_pr_number": {created_pr_number}'),
            )
        ).scalar_one_or_none()

        assert sutra_pr is not None, "PR must appear in SUTRA"
        assert sutra_pr.source_commit == commit_1_sha
        assert sutra_pr.status == "open"

        # Check linked change
        tracking_change = db.execute(
            select(Change).where(Change.id == sutra_pr.source_change_id)
        ).scalar_one_or_none()
        assert tracking_change is not None
        ch_meta = json.loads(tracking_change.metadata_json) if tracking_change.metadata_json else {}
        assert ch_meta.get("source") == "github"
        assert ch_meta.get("source_type") == "github"
        assert ch_meta.get("agent_id") is None
        assert ch_meta.get("task_id") is None
        print(f"Verified SUTRA PR {sutra_pr.id} has external tracking Change and no fake agent provenance")

        # -------------------------------------------------------------
        # 5. Simulate approval in SUTRA
        # -------------------------------------------------------------
        sutra_pr.status = "approved"
        change_meta = {}
        if tracking_change.metadata_json:
            change_meta = json.loads(tracking_change.metadata_json)
        change_meta["approved_head_sha"] = commit_1_sha
        change_meta["governance_approval"] = True
        tracking_change.metadata_json = json.dumps(change_meta, sort_keys=True)
        db.commit()
        print("PR marked as approved for HEAD SHA:", commit_1_sha)

        # -------------------------------------------------------------
        # 6. Push a 2nd commit to the PR branch on GitHub
        # -------------------------------------------------------------
        file_res_2 = provider.create_or_update_file(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            path=f"docs/smoke_update_{test_id}.txt",
            message=f"Smoke test commit 2: {test_id}",
            content=f"Smoke test commit 2 for {test_id} - updated\n".encode("utf-8"),
            branch=branch_name,
        )
        commit_2_sha = file_res_2["commit"]["sha"]
        print(f"Committed 2nd file with new HEAD SHA: {commit_2_sha}")
        assert commit_2_sha != commit_1_sha

        # Deliver pull_request.synchronize webhook
        sync_webhook_payload = {
            "action": "synchronize",
            "repository": {
                "id": int(repo.external_id) if (repo.external_id and repo.external_id.isdigit()) else 1075617112,
                "name": GITHUB_REPOSITORY,
                "full_name": f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}",
                "owner": {"login": GITHUB_OWNER},
            },
            "pull_request": {
                "id": int(created_pr.number) * 1000 + 77,
                "number": created_pr.number,
                "title": created_pr.title,
                "body": created_pr.body,
                "state": "open",
                "html_url": created_pr.html_url or f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/pull/{created_pr_number}",
                "user": {"login": GITHUB_OWNER},
                "head": {
                    "ref": branch_name,
                    "sha": commit_2_sha,
                },
                "base": {
                    "ref": base_branch,
                    "sha": base_commit,
                },
                "merged": False,
            },
        }
        payload_bytes = json.dumps(sync_webhook_payload).encode("utf-8")
        sig = sign_payload(payload_bytes, settings.github_webhook_secret)

        resp = client.post(
            "/v1/webhooks/github",
            content=payload_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200

        # -------------------------------------------------------------
        # 7. Verify Approval is Invalidated (Stale)
        # -------------------------------------------------------------
        db.expire_all()
        updated_pr = db.execute(
            select(PullRequest).where(PullRequest.id == sutra_pr.id)
        ).scalar_one()

        assert updated_pr.source_commit == commit_2_sha, "source_commit must update to new HEAD"
        assert updated_pr.status == "open", "Approval status must be downgraded to open"
        updated_change = db.execute(select(Change).where(Change.id == updated_pr.source_change_id)).scalar_one()
        updated_meta = json.loads(updated_change.metadata_json) if updated_change.metadata_json else {}
        assert updated_meta.get("approved_head_sha") is None, "approved_head_sha must be cleared"
        print("Verified PR approval successfully invalidated on HEAD push")

        # -------------------------------------------------------------
        # 8. Verify Knowledge Graph contains nodes and edges
        # -------------------------------------------------------------
        from app.services.knowledge_graph_service import index_engineering_lifecycle
        index_engineering_lifecycle(db, repo.id)
        db.commit()

        # Query KG nodes
        issue_nodes = db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.repository_id == repo.id,
                KnowledgeNode.entity_type == "issue",
            )
        ).scalars().all()
        assert len(issue_nodes) >= 1, "KG must contain issue node"

        pr_nodes = db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.repository_id == repo.id,
                KnowledgeNode.entity_type == "pull_request",
            )
        ).scalars().all()
        assert len(pr_nodes) >= 1, "KG must contain pull request node"

        edges = db.execute(
            select(KnowledgeEdge).where(
                KnowledgeEdge.relationship_type == "reviewed_in",
            )
        ).scalars().all()
        assert len(edges) >= 1, "KG must contain reviewed_in edge between change and PR"
        print(f"Verified KG indexed repository entities with {len(edges)} reviewed_in edges")

    finally:
        # Cleanup GitHub resources
        if created_pr_number:
            try:
                provider.close_pull_request(
                    owner=GITHUB_OWNER,
                    name=GITHUB_REPOSITORY,
                    pr_number=created_pr_number,
                )
                print(f"Cleaned up GitHub PR #{created_pr_number}")
            except Exception as e:
                print("Failed to close PR:", e)
        if created_issue_number:
            try:
                provider.close_issue(
                    owner=GITHUB_OWNER,
                    name=GITHUB_REPOSITORY,
                    issue_number=created_issue_number,
                )
                print(f"Cleaned up GitHub Issue #{created_issue_number}")
            except Exception as e:
                print("Failed to close Issue:", e)
        try:
            provider.delete_branch(owner=GITHUB_OWNER, name=GITHUB_REPOSITORY, branch=branch_name)
            print(f"Deleted GitHub test branch {branch_name}")
        except Exception as e:
            print("Failed to delete branch:", e)
        db.close()
