from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.actor import Actor
from app.models.repository import Repository
from app.models.user import User
from app.core.security import hash_password

from app.providers.base import (
    ProviderIssue,
    ProviderIssueComment,
)


def make_user(db):
    user_id = str(uuid4())

    user = User(
        id=user_id,
        username=f"user-{user_id[:8]}",
        email=f"{user_id[:8]}@example.com",
        password_hash=hash_password("password"),
    )

    db.add(user)

    actor = Actor(
        id=user.id,
        type="user",
        name=user.username,
    )

    db.add(actor)
    db.commit()

    return user


def make_repo(db, owner_id, repo_name="issue-repo"):
    repo = Repository(
        owner_id=owner_id,
        name=repo_name,
        slug=repo_name,
        description="test repo",
        storage_key=f"test-storage-{uuid4().hex}",
        provider_type="github",
        provider_owner="fake-owner",
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    return repo


class FakeGitHubRepositoryProvider:
    """
    In-memory GitHub provider used for API integration tests.

    This deliberately behaves like the real GitHub provider at the
    RepositoryProvider boundary while avoiding network calls.
    """

    def __init__(self):
        self.issues: dict[int, dict] = {}
        self.comments: dict[int, list[dict]] = {}

        self.next_issue_number = 1
        self.next_issue_id = 1000
        self.next_comment_id = 5000

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _issue_to_provider(self, item: dict) -> ProviderIssue:
        return ProviderIssue(
            id=str(item["id"]),
            number=item["number"],
            title=item["title"],
            body=item["body"],
            state=item["state"],
            author_login=item["author_login"],
            author_name=item["author_name"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            closed_at=item["closed_at"],
            html_url=item["html_url"],
            labels=item["labels"],
        )

    def _comment_to_provider(self, item: dict) -> ProviderIssueComment:
        return ProviderIssueComment(
            id=str(item["id"]),
            issue_number=item["issue_number"],
            body=item["body"],
            author_login=item["author_login"],
            author_name=item["author_name"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            html_url=item["html_url"],
        )

    # =========================================================
    # ISSUES
    # =========================================================

    def create_issue(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
    ) -> ProviderIssue:
        now = self._now()

        number = self.next_issue_number
        self.next_issue_number += 1

        issue_id = self.next_issue_id
        self.next_issue_id += 1

        item = {
            "id": issue_id,
            "number": number,
            "title": title,
            "body": body,
            "state": "open",
            "author_login": "sutra-test-user",
            "author_name": "SUTRA Test User",
            "created_at": now,
            "updated_at": now,
            "closed_at": None,
            "html_url": (
                f"https://github.com/{owner}/{name}"
                f"/issues/{number}"
            ),
            "labels": [],
        }

        self.issues[number] = item
        self.comments[number] = []

        return self._issue_to_provider(item)

    def get_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ):
        item = self.issues.get(issue_number)

        if item is None:
            return None

        return self._issue_to_provider(item)

    def list_issues(
        self,
        owner: str,
        name: str,
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ):
        items = list(self.issues.values())

        if state in {"open", "closed"}:
            items = [
                item
                for item in items
                if item["state"] == state
            ]

        items.sort(
            key=lambda item: item["created_at"],
            reverse=True,
        )

        items = items[offset: offset + limit]

        return [
            self._issue_to_provider(item)
            for item in items
        ]

    # =========================================================
    # COMMENTS
    # =========================================================

    def create_issue_comment(
        self,
        owner: str,
        name: str,
        issue_number: int,
        body: str,
    ) -> ProviderIssueComment:
        if issue_number not in self.issues:
            raise ValueError("Issue not found")

        now = self._now()

        comment_id = self.next_comment_id
        self.next_comment_id += 1

        item = {
            "id": comment_id,
            "issue_number": issue_number,
            "body": body,
            "author_login": "sutra-test-user",
            "author_name": "SUTRA Test User",
            "created_at": now,
            "updated_at": now,
            "html_url": (
                f"https://github.com/{owner}/{name}"
                f"/issues/{issue_number}#comment-{comment_id}"
            ),
        }

        self.comments[issue_number].append(item)

        return self._comment_to_provider(item)

    def list_issue_comments(
        self,
        owner: str,
        name: str,
        issue_number: int,
        limit: int = 50,
        offset: int = 0,
    ):
        comments = self.comments.get(issue_number, [])

        comments = comments[offset: offset + limit]

        return [
            self._comment_to_provider(comment)
            for comment in comments
        ]

    # =========================================================
    # STATE
    # =========================================================

    def close_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> ProviderIssue:
        item = self.issues.get(issue_number)

        if item is None:
            raise ValueError("Issue not found")

        now = self._now()

        item["state"] = "closed"
        item["closed_at"] = now
        item["updated_at"] = now

        return self._issue_to_provider(item)

    def reopen_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> ProviderIssue:
        item = self.issues.get(issue_number)

        if item is None:
            raise ValueError("Issue not found")

        now = self._now()

        item["state"] = "open"
        item["closed_at"] = None
        item["updated_at"] = now

        return self._issue_to_provider(item)


@pytest.fixture
def fake_github_provider(monkeypatch):
    """
    Replace the real GitHub provider used by the Issues router.
    """

    from app.api import issues as issues_api

    provider = FakeGitHubRepositoryProvider()

    monkeypatch.setattr(
        issues_api,
        "_github_provider",
        lambda repository: provider,
    )

    return provider


def test_issues_api(
    client,
    db,
    fake_github_provider,
):
    user = make_user(db)
    repo = make_repo(db, user.id)

    # =========================================================
    # LOGIN
    # =========================================================

    login_resp = client.post(
        "/v1/auth/login",
        json={
            "login": user.email,
            "password": "password",
        },
    )

    assert login_resp.status_code == 200

    user_token = login_resp.json()["access_token"]

    auth_headers = {
        "Authorization": f"Bearer {user_token}",
    }

    base_url = (
        f"/v1/repositories/"
        f"{user.username}/{repo.name}/issues"
    )

    # =========================================================
    # 1. CREATE ISSUE
    # =========================================================

    create_resp = client.post(
        base_url,
        headers=auth_headers,
        json={
            "title": "Bug in API",
            "body": "It crashes.",
        },
    )

    assert create_resp.status_code == 201

    issue = create_resp.json()

    assert issue["title"] == "Bug in API"
    assert issue["body"] == "It crashes."
    assert issue["status"] == "open"

    assert issue["github_issue_number"] == 1
    assert issue["github_issue_id"] == "1000"
    assert issue["github_html_url"].endswith("/issues/1")

    assert issue["source_type"] == "human"

    # The issue must actually exist in the provider substrate.
    assert 1 in fake_github_provider.issues

    # =========================================================
    # 2. CREATE SECOND ISSUE
    # =========================================================

    second_resp = client.post(
        base_url,
        headers=auth_headers,
        json={
            "title": "Second issue",
            "body": "Another problem.",
        },
    )

    assert second_resp.status_code == 201

    second_issue = second_resp.json()

    assert second_issue["github_issue_number"] == 2
    assert second_issue["source_type"] == "human"

    # =========================================================
    # 3. LIST ISSUES
    # =========================================================

    list_resp = client.get(
        base_url,
        headers=auth_headers,
    )

    assert list_resp.status_code == 200

    issues = list_resp.json()

    assert len(issues) == 2

    numbers = {
        item["github_issue_number"]
        for item in issues
    }

    assert numbers == {1, 2}

    # =========================================================
    # 4. GET ISSUE
    # =========================================================

    get_resp = client.get(
        f"{base_url}/1",
        headers=auth_headers,
    )

    assert get_resp.status_code == 200

    fetched_issue = get_resp.json()

    assert fetched_issue["github_issue_number"] == 1
    assert fetched_issue["title"] == "Bug in API"
    assert fetched_issue["body"] == "It crashes."
    assert fetched_issue["status"] == "open"

    # =========================================================
    # 5. ADD COMMENT
    # =========================================================

    comment_resp = client.post(
        f"{base_url}/1/comments",
        headers=auth_headers,
        json={
            "body": "I will investigate this.",
        },
    )

    assert comment_resp.status_code == 201

    comment = comment_resp.json()

    assert comment["body"] == "I will investigate this."
    assert comment["issue_id"] == issue["id"]

    assert comment["github_comment_id"] == "5000"
    assert comment["github_author_login"] == "sutra-test-user"

    # =========================================================
    # 6. LIST COMMENTS
    # =========================================================

    comments_resp = client.get(
        f"{base_url}/1/comments",
        headers=auth_headers,
    )

    assert comments_resp.status_code == 200

    comments = comments_resp.json()

    assert len(comments) == 1
    assert comments[0]["body"] == "I will investigate this."

    # =========================================================
    # 7. CLOSE ISSUE
    # =========================================================

    close_resp = client.patch(
        f"{base_url}/1/status",
        headers=auth_headers,
        json={
            "status": "closed",
            "comment": "Fix completed.",
        },
    )

    assert close_resp.status_code == 200

    close_data = close_resp.json()

    assert close_data["status"] == "ok"
    assert close_data["issue_status"] == "closed"
    assert close_data["github_issue_number"] == 1

    # Verify provider state.
    provider_issue = fake_github_provider.get_issue(
        owner="fake-owner",
        name=repo.name,
        issue_number=1,
    )

    assert provider_issue is not None
    assert provider_issue.state == "closed"

    # =========================================================
    # 8. VERIFY CLOSED THROUGH API
    # =========================================================

    closed_get_resp = client.get(
        f"{base_url}/1",
        headers=auth_headers,
    )

    assert closed_get_resp.status_code == 200
    assert closed_get_resp.json()["status"] == "closed"

    # =========================================================
    # 9. REOPEN ISSUE
    # =========================================================

    reopen_resp = client.patch(
        f"{base_url}/1/status",
        headers=auth_headers,
        json={
            "status": "open",
        },
    )

    assert reopen_resp.status_code == 200

    reopen_data = reopen_resp.json()

    assert reopen_data["status"] == "ok"
    assert reopen_data["issue_status"] == "open"
    assert reopen_data["github_issue_number"] == 1

    # =========================================================
    # 10. VERIFY REOPENED
    # =========================================================

    reopened_get_resp = client.get(
        f"{base_url}/1",
        headers=auth_headers,
    )

    assert reopened_get_resp.status_code == 200
    assert reopened_get_resp.json()["status"] == "open"

    # =========================================================
    # 11. VERIFY COMMENT WAS MIRRORED TO PROVIDER
    # =========================================================

    provider_comments = (
        fake_github_provider.list_issue_comments(
            owner="fake-owner",
            name=repo.name,
            issue_number=1,
        )
    )

    assert len(provider_comments) >= 2

    bodies = {
        comment.body
        for comment in provider_comments
    }

    assert "I will investigate this." in bodies
    assert any(
        "Fix completed." in body
        for body in bodies
    )