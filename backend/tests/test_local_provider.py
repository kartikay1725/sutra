import pytest
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.user import User
from app.core.security import hash_password
from app.providers.local.repository import LocalRepositoryProvider
from app.providers.local.credentials import LocalCredentialProvider
from app.providers.local.checks import LocalCheckProvider
from app.providers.local.events import LocalWebhookAdapter
from app.providers.registry import ProviderRegistry
from app.providers.checks import CheckRunReport, CheckStatus, CheckConclusion


def create_user(db, username="alice"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("secret123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_provider_registry_resolution(db):
    user = create_user(db, "reg_user")
    repo = Repository(
        owner_id=user.id,
        name="test-repo",
        slug="test-repo",
        storage_key="test-repo-key",
        default_branch="main",
        visibility="private",
    )
    db.add(repo)
    db.commit()

    local_repo = LocalRepositoryProvider(db)
    local_cred = LocalCredentialProvider(db)
    local_check = LocalCheckProvider(db)
    local_wh = LocalWebhookAdapter()

    registry = ProviderRegistry(
        repository_providers={"local": local_repo},
        credential_providers={"local": local_cred},
        webhook_adapters={"local": local_wh},
        check_providers={"local": local_check},
        default_provider="local",
    )

    resolved_repo_p = registry.get_repository_provider(repo)
    assert isinstance(resolved_repo_p, LocalRepositoryProvider)

    resolved_cred_p = registry.get_credential_provider(repo)
    assert isinstance(resolved_cred_p, LocalCredentialProvider)

    resolved_check_p = registry.get_check_provider(repo)
    assert isinstance(resolved_check_p, LocalCheckProvider)


def test_local_repository_metadata(db):
    user = create_user(db, "meta_user")
    repo = Repository(
        owner_id=user.id,
        name="meta-repo",
        slug="meta-repo",
        storage_key="meta-repo-key",
        default_branch="main",
        visibility="private",
    )
    db.add(repo)
    db.commit()

    provider = LocalRepositoryProvider(db)
    meta = provider.get_repository_metadata(user.username, "meta-repo")

    assert meta.provider_type == "local"
    assert meta.name == "meta-repo"
    assert meta.default_branch == "main"
    assert meta.is_private is True
    assert meta.capabilities["pre_receive_hook"] is True
    assert meta.capabilities["rulesets"] is False


def test_local_credential_issuance_and_revocation(db):
    user = create_user(db, "cred_user")
    agent = Agent(
        owner_id=user.id,
        name="test-agent",
        token_hash="hash",
        token_prefix="sutra_agent_1234",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    session = AgentSession(
        agent_id=agent.id,
        token_hash="hash2",
        token_prefix="sutra_session_1234",
        status="active",
        expires_at=now + timedelta(minutes=15),
    )
    db.add(session)
    db.commit()

    cred_provider = LocalCredentialProvider(db)
    downstream_cred = cred_provider.issue_agent_token(
        agent_id=agent.id,
        session_id=session.id,
        owner=user.username,
        repo="my-repo",
        sutra_capabilities=["repository.read", "repository.write"],
        max_ttl_seconds=300,
    )

    assert downstream_cred.token_type == "basic"
    assert downstream_cred.effective_ttl_seconds <= 600
    assert downstream_cred.permissions["repository.read"] == "true"
    assert downstream_cred.permissions["repository.write"] == "true"

    # Revocation test
    revoked = cred_provider.revoke_credential(session.id, downstream_cred.token)
    assert revoked is True

    db.refresh(session)
    assert session.status == "revoked"


def test_local_check_provider(db):
    check_provider = LocalCheckProvider(db)
    report = CheckRunReport(
        check_name="SUTRA Policy Engine",
        head_sha="abcdef1234567890abcdef1234567890abcdef12",
        status=CheckStatus.COMPLETED,
        conclusion=CheckConclusion.SUCCESS,
        title="Policy Passed",
        summary="All deterministic policy checks passed.",
        details_url="http://localhost:8000/changes/1",
        external_id="change-1",
    )

    ref = check_provider.report_check_run("owner", "repo", report)
    assert "local-check:" in ref
    assert "completed" in ref
