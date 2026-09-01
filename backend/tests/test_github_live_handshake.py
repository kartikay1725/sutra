import os
import pytest
from app.core.config import get_settings
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider
from app.providers.github.credentials import GitHubCredentialProvider


def test_live_github_app_handshake():
    settings = get_settings()

    app_id = settings.github_app_id
    pem = settings.github_private_key_pem
    owner = settings.github_test_repo_owner or "kartikay1725"
    repo = settings.github_test_repo_name or "sutra-github-e2e-dev"

    assert app_id is not None and str(app_id).strip() != "", "GITHUB_APP_ID is not configured in .env"
    assert pem is not None and "BEGIN" in pem and "END" in pem, "GITHUB_PRIVATE_KEY_PEM is not valid in .env"

    auth_service = GitHubAppAuthService(
        app_id=str(app_id),
        private_key_pem=pem,
        base_url=settings.github_api_base_url,
    )

    # 1. Verify App JWT Generation
    jwt_token = auth_service.generate_app_jwt(ttl_seconds=300)
    assert isinstance(jwt_token, str) and len(jwt_token) > 50

    # 2. Verify Live App Identity via GitHub API
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    import httpx
    with httpx.Client(base_url=settings.github_api_base_url, timeout=15.0) as client:
        res_app = client.get("/app", headers=headers)
        assert res_app.status_code == 200, f"GitHub App authentication failed: {res_app.status_code} {res_app.text}"
        app_info = res_app.json()
        assert str(app_info.get("id")) == str(app_id)

        # 3. Verify Installation Discovery on test repo
        inst_id = auth_service.get_installation_id(owner=owner, repo=repo)
        assert isinstance(inst_id, int) and inst_id > 0

        # 4. Verify Scoped Installation Token Issuance (<= 10 min SUTRA horizon)
        cred_provider = GitHubCredentialProvider(auth_service)
        cred = cred_provider.issue_agent_token(
            agent_id="test-agent-live",
            session_id="test-session-live",
            owner=owner,
            repo=repo,
            sutra_capabilities=["repository.read", "repository.write"],
            max_ttl_seconds=600,
        )

        assert cred.token.startswith("ghs_")
        assert cred.effective_ttl_seconds == 600
        assert cred.permissions.get("contents") == "write"
        assert "pull_requests" not in cred.permissions  # Invariant: minimal mapping

        # 5. Verify Live Repository Metadata Query using GitHubRepositoryProvider
        gh_repo_provider = GitHubRepositoryProvider(auth_service=auth_service)
        meta = gh_repo_provider.get_repository_metadata(owner=owner, name=repo)
        assert meta.provider_type == "github"
        assert meta.name == repo
        assert meta.default_branch == "main"
        assert meta.capabilities["check_runs"] is True
