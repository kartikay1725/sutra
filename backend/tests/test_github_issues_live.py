from uuid import uuid4

import pytest

from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider
from app.core.config import settings


OWNER = "kartikay1725"
REPO = "dam-project"


@pytest.fixture
def provider() -> GitHubRepositoryProvider:
    assert settings.github_app_id
    assert settings.github_private_key_pem

    auth = GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )

    return GitHubRepositoryProvider(
        auth_service=auth,
        base_url=settings.github_api_base_url,
    )


def test_live_github_issue_lifecycle(provider):
    marker = uuid4().hex[:8]

    title = f"[SUTRA E2E] Issue lifecycle {marker}"
    body = (
        "Temporary issue created by the SUTRA GitHub "
        "Issues provider E2E test."
    )

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    issue = provider.create_issue(
        owner=OWNER,
        name=REPO,
        title=title,
        body=body,
    )

    assert issue.number > 0
    assert issue.title == title
    assert issue.state == "open"
    assert issue.html_url

    print(
        f"\nCreated GitHub issue #{issue.number}: "
        f"{issue.html_url}"
    )

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------

    fetched = provider.get_issue(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
    )

    assert fetched is not None
    assert fetched.id == issue.id
    assert fetched.number == issue.number
    assert fetched.title == title
    assert fetched.state == "open"

    # ---------------------------------------------------------
    # COMMENT
    # ---------------------------------------------------------

    comment = provider.create_issue_comment(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
        body=(
            "SUTRA provider E2E comment "
            f"{marker}"
        ),
    )

    assert comment.id
    assert comment.issue_number == issue.number
    assert marker in comment.body

    # ---------------------------------------------------------
    # LIST COMMENTS
    # ---------------------------------------------------------

    comments = provider.list_issue_comments(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
    )

    assert any(
        marker in c.body
        for c in comments
    )

    # ---------------------------------------------------------
    # CLOSE
    # ---------------------------------------------------------

    closed = provider.close_issue(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
    )

    assert closed.number == issue.number
    assert closed.state == "closed"

    # ---------------------------------------------------------
    # VERIFY CLOSED
    # ---------------------------------------------------------

    fetched_closed = provider.get_issue(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
    )

    assert fetched_closed is not None
    assert fetched_closed.state == "closed"

    # ---------------------------------------------------------
    # REOPEN
    # ---------------------------------------------------------

    reopened = provider.reopen_issue(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
    )

    assert reopened.number == issue.number
    assert reopened.state == "open"

    # ---------------------------------------------------------
    # VERIFY REOPENED
    # ---------------------------------------------------------

    fetched_reopened = provider.get_issue(
        owner=OWNER,
        name=REPO,
        issue_number=issue.number,
    )

    assert fetched_reopened is not None
    assert fetched_reopened.state == "open"

    print(
        f"Completed GitHub issue lifecycle for "
        f"#{issue.number}"
    )