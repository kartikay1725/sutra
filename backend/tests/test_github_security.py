import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.models.repository import Repository
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.user import User
from app.core.security import hash_password
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.credentials import GitHubCredentialProvider
from app.providers.github.repository import GitHubRepositoryProvider
from app.providers.github.events import GitHubWebhookAdapter
from app.providers.checks import CheckRunReport, CheckStatus, CheckConclusion
from app.services.change_policy_service import ChangePolicyService, PolicyDecision
from app.services.check_service import CheckService
from app.providers.registry import ProviderRegistry


def generate_rsa_key_pem():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


def test_github_app_jwt_generation():
    pem = generate_rsa_key_pem()
    auth_service = GitHubAppAuthService(app_id="12345", private_key_pem=pem)
    jwt_token = auth_service.generate_app_jwt(ttl_seconds=300)

    assert isinstance(jwt_token, str)
    assert len(jwt_token) > 50
    # Ensure sensitive private key is never contained in the token
    assert "BEGIN PRIVATE KEY" not in jwt_token


def test_minimal_capability_mapping_no_merge_rights():
    pem = generate_rsa_key_pem()
    auth_service = GitHubAppAuthService(app_id="12345", private_key_pem=pem)
    cred_provider = GitHubCredentialProvider(auth_service)

    # 1. repository.read
    perms_read = cred_provider._map_capabilities_to_permissions(["repository.read"])
    assert perms_read == {"contents": "read", "metadata": "read"}
    assert "pull_requests" not in perms_read
    assert "administration" not in perms_read

    # 2. repository.write
    perms_write = cred_provider._map_capabilities_to_permissions(["repository.write"])
    assert perms_write == {"contents": "write", "metadata": "read"}
    # Mandatory invariant: repository.write MUST NOT grant pull_requests:write or merge
    assert "pull_requests" not in perms_write
    assert perms_write.get("contents") == "write"


def test_effective_max_ttl_bounded_to_10_minutes():
    pem = generate_rsa_key_pem()
    mock_client = MagicMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.json.return_value = {"id": 999}
    mock_client.post.return_value.status_code = 201
    mock_client.post.return_value.json.return_value = {
        "token": "ghs_test_token_12345",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "permissions": {"contents": "write"},
    }

    auth_service = GitHubAppAuthService(app_id="12345", private_key_pem=pem, client=mock_client)
    cred_provider = GitHubCredentialProvider(auth_service)

    # Request a 2-hour TTL — SUTRA must clamp it to 600s (10 min)
    cred = cred_provider.issue_agent_token(
        agent_id="agent-1",
        session_id="session-1",
        owner="org",
        repo="repo",
        sutra_capabilities=["repository.write"],
        max_ttl_seconds=7200,
    )

    assert cred.effective_ttl_seconds == 600
    time_diff = (cred.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 590 <= time_diff <= 610


def test_active_downstream_token_revocation():
    pem = generate_rsa_key_pem()
    mock_client = MagicMock()
    mock_client.delete.return_value.status_code = 204

    auth_service = GitHubAppAuthService(app_id="12345", private_key_pem=pem, client=mock_client)
    cred_provider = GitHubCredentialProvider(auth_service)

    revoked = cred_provider.revoke_credential("session-1", "ghs_test_token_12345")
    assert revoked is True
    mock_client.delete.assert_called_once_with(
        "/installation/token",
        headers={
            "Authorization": "Bearer ghs_test_token_12345",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def test_untracked_feature_push_cannot_become_mergeable(db):
    # Setup human owner, agent, repository
    user = User(username="carol", email="carol@example.com", password_hash=hash_password("pw"))
    db.add(user)
    db.commit()

    repo = Repository(
        owner_id=user.id,
        name="github-backed-repo",
        slug="github-backed-repo",
        storage_key="github-repo-key",
        default_branch="main",
        visibility="private",
    )
    db.add(repo)
    db.commit()

    agent = Agent(
        owner_id=user.id,
        name="unauthorized-agent",
        token_hash="hash",
        token_prefix="sutra_agent_9999",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities="[]",
    )
    db.add(actor)
    db.commit()

    # Agent pushes a commit to a feature branch on GitHub
    unauthorized_sha = "1111222233334444555566667777888899990000"
    change = Change(
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Unauthorized push test",
        status="proposed",
        resulting_commit=unauthorized_sha,
        operation_key="op-unauth-1",
    )
    db.add(change)
    db.commit()

    # Policy evaluation must BLOCK because agent lacks repository.read and change.create capabilities
    policy_service = ChangePolicyService(db)
    decision = policy_service.evaluate(change)

    assert decision.decision == ChangePolicyService.BLOCK
    assert "lacks required capabilities" in decision.reason.lower()

    # SUTRA CheckService publishes FAILURE / BLOCK Check Run to GitHub
    mock_check_provider = MagicMock()
    mock_check_provider.report_check_run.return_value = "check-run-12345"

    registry = ProviderRegistry(
        repository_providers={},
        credential_providers={},
        webhook_adapters={},
        check_providers={"local": mock_check_provider},
        default_provider="local",
    )

    check_service = CheckService(db, registry)
    check_id = check_service.publish_change_policy_check(
        change=change,
        repository=repo,
        policy_decision=decision,
        review_approved=False,
    )

    assert check_id == "check-run-12345"
    mock_check_provider.report_check_run.assert_called_once()
    call_args = mock_check_provider.report_check_run.call_args[1]
    report: CheckRunReport = call_args["report"]

    # Invariant: Check Run conclusion MUST be FAILURE, preventing GitHub PR merge
    assert report.status == CheckStatus.COMPLETED
    assert report.conclusion == CheckConclusion.FAILURE
    assert "blocked" in report.summary.lower()
