import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.repository import Repository
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.core.security import hash_password, create_access_token
from app.core.config import settings
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.events import GitHubWebhookAdapter
from app.providers.github.repository import GitHubRepositoryProvider
from app.providers.github.credentials import GitHubCredentialProvider
from app.providers.github.checks import GitHubCheckProvider
from app.providers.checks import CheckRunReport, CheckStatus, CheckConclusion
from app.providers.registry import ProviderRegistry
from app.services.change_policy_service import ChangePolicyService
from app.services.check_service import CheckService


def test_complete_github_lifecycle_e2e(db, client):
    # 1. Setup Human 1 (Author/Owner) and Human 2 (Reviewer)
    human_owner = User(
        username="alice",
        email="alice@example.com",
        password_hash=hash_password("password123"),
    )
    human_reviewer = User(
        username="bob",
        email="bob@example.com",
        password_hash=hash_password("password123"),
    )
    db.add_all([human_owner, human_reviewer])
    db.commit()

    owner_actor = Actor(
        id=human_owner.id,
        owner_id=human_owner.id,
        type="human",
        name=human_owner.username,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    reviewer_actor = Actor(
        id=human_reviewer.id,
        owner_id=human_reviewer.id,
        type="human",
        name=human_reviewer.username,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add_all([owner_actor, reviewer_actor])
    db.commit()

    # 2. Setup GitHub-backed Repository
    repo = Repository(
        owner_id=human_owner.id,
        name="web-platform",
        slug="web-platform",
        storage_key="github-web-platform-key",
        default_branch="main",
        visibility="private",
    )
    # Set provider_type to github
    setattr(repo, "provider_type", "github")
    db.add(repo)
    db.commit()

    # 3. Create Agent and grant explicit repository access
    agent = Agent(
        owner_id=human_owner.id,
        name="codex-builder",
        token_hash=hash_password("sutra_agent_secret_permanent"),
        token_prefix="sutra_agent_perm",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=human_owner.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create", "change.commit"]',
    )
    db.add(agent_actor)

    repo_access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions='["repository.read", "repository.write", "change.create", "change.commit"]',
        enabled=True,
    )
    db.add(repo_access)
    db.commit()

    # 4. Agent creates SUTRA AgentSession
    now = datetime.now(timezone.utc)
    raw_session_token = "sutra_session_abcdef1234567890abcdef123456"
    session = AgentSession(
        agent_id=agent.id,
        token_hash=hash_password(raw_session_token),
        token_prefix=raw_session_token[:32],
        status="active",
        expires_at=now + timedelta(minutes=15),
    )
    db.add(session)
    db.commit()

    # 5. Agent requests downstream GitHub token via SUTRA Token Broker endpoint
    with patch("app.providers.github.auth.GitHubAppAuthService.get_installation_id", return_value=12345), \
         patch("app.providers.github.auth.GitHubAppAuthService.create_installation_token", return_value={
             "token": "ghs_mock_installation_token_777",
             "expires_at": (now + timedelta(hours=1)).isoformat(),
             "permissions": {"contents": "write"},
         }):

        res_token = client.post(
            f"/v1/repositories/{human_owner.username}/{repo.slug}/token",
            headers={"Authorization": f"Bearer {raw_session_token}"},
            json={
                "capabilities": ["repository.read", "repository.write"],
                "max_ttl_seconds": 600,
            },
        )
        assert res_token.status_code == 200
        token_resp = res_token.json()
        assert token_resp["token"] == "ghs_mock_installation_token_777"
        assert token_resp["effective_ttl_seconds"] == 600
        assert "x-access-token" in token_resp["clone_url"]

    # 6. GitHub emits push webhook to SUTRA
    head_sha = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    webhook_payload = {
        "repository": {
            "name": repo.slug,
            "owner": {"login": human_owner.username},
        },
        "ref": "refs/heads/agent/feature-login",
        "before": "0000000000000000000000000000000000000000",
        "after": head_sha,
        "created": True,
        "deleted": False,
        "forced": False,
        "pusher": {"name": human_owner.username},
        "commits": [{"id": head_sha}],
    }
    payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    secret = getattr(settings, "github_webhook_secret", None) or settings.jwt_secret
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    res_wh = client.post(
        "/v1/webhooks/github",
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
        content=payload_bytes,
    )
    assert res_wh.status_code == 200
    assert res_wh.json()["status"] == "processed"

    # 7. Agent records Change in SUTRA
    change = Change(
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Implement robust login flow",
        status="recorded",
        resulting_commit=head_sha,
        operation_key="op-e2e-gh-1",
    )
    db.add(change)
    db.commit()

    # 8. SUTRA executes deterministic policy
    policy_service = ChangePolicyService(db)
    decision = policy_service.evaluate(change)
    # Agent has required capabilities
    assert decision.decision in {ChangePolicyService.ALLOW, ChangePolicyService.REVIEW}

    # 9. Create PR in SUTRA
    pr = PullRequest(
        repository_id=repo.id,
        author_id=agent_actor.id,
        source_change_id=change.id,
        title="Implement robust login flow",
        description="Feature implementation",
        target_branch="main",
        source_commit=head_sha,
        status=PullRequest.STATUS_OPEN,
    )
    db.add(pr)
    db.commit()

    # 10. Check Run published to GitHub (Requires human review approval)
    mock_check_provider = MagicMock()
    mock_check_provider.report_check_run.return_value = "check-100"
    registry = ProviderRegistry(
        repository_providers={},
        credential_providers={},
        webhook_adapters={},
        check_providers={"github": mock_check_provider, "local": mock_check_provider},
        default_provider="github",
    )

    check_service = CheckService(db, registry)
    check_service.publish_change_policy_check(
        change=change,
        repository=repo,
        policy_decision=decision,
        review_approved=False,
    )
    mock_check_provider.report_check_run.assert_called_once()
    initial_report = mock_check_provider.report_check_run.call_args[1]["report"]
    # Check is in progress / action required before human approval
    assert initial_report.status == CheckStatus.IN_PROGRESS
    assert initial_report.conclusion == CheckConclusion.ACTION_REQUIRED

    # 11. Human 2 (Reviewer) approves the review in SUTRA
    review = ChangeReview(
        change_id=change.id,
        requested_by=human_owner.id,
        reviewer_id=human_reviewer.id,
        status="approved",
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    pr.status = PullRequest.STATUS_APPROVED
    db.commit()

    # 12. SUTRA publishes SUCCESS Check Run now that human review is approved
    check_service.publish_change_policy_check(
        change=change,
        repository=repo,
        policy_decision=decision,
        review_approved=True,
    )
    approved_report = mock_check_provider.report_check_run.call_args[1]["report"]
    assert approved_report.status == CheckStatus.COMPLETED
    assert approved_report.conclusion == CheckConclusion.SUCCESS

    # 13. Human Owner executes Merge via GitHubRepositoryProvider
    mock_http_client = MagicMock()
    mock_http_client.put.return_value.status_code = 200
    mock_http_client.put.return_value.json.return_value = {
        "sha": "merge_commit_sha_99999",
        "merged": True,
        "message": "Pull Request successfully merged",
    }

    with patch("app.providers.github.auth.GitHubAppAuthService.get_installation_id", return_value=12345), \
         patch("app.providers.github.auth.GitHubAppAuthService.create_installation_token", return_value={"token": "ghs_merge_token"}):

        gh_repo_provider = GitHubRepositoryProvider(
            auth_service=GitHubAppAuthService(app_id="1", private_key_pem="key"),
            client=mock_http_client,
        )

        merge_result = gh_repo_provider.merge_pull_request(
            owner=human_owner.username,
            name=repo.slug,
            pr_number=1,
            commit_title="Merge pull request #1",
            commit_message="Merged via SUTRA Control Plane",
            expected_head_sha=head_sha,
            method="squash",
        )

        assert merge_result.success is True
        assert merge_result.merge_commit_sha == "merge_commit_sha_99999"

        # 14. Update SUTRA PR state to MERGED
        pr.status = PullRequest.STATUS_MERGED
        pr.target_commit = merge_result.merge_commit_sha
        pr.merged_at = datetime.now(timezone.utc)
        db.commit()

        assert pr.status == PullRequest.STATUS_MERGED
        assert pr.target_commit == "merge_commit_sha_99999"
