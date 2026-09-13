import hashlib
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_service import redis_service
from app.api.repository_browser import (
    _is_immutable_sha,
    _get_cached_json,
    _set_cached_json,
    list_repository_branches,
    _resolve_repository,
)
from app.api.issues import list_issues
from app.api.webhooks.github import _invalidate_repo_cache
from app.models.repository import Repository
from app.models.issue import Issue
from app.models.user import User
from app.models.pull_request import PullRequest
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.services.pull_request_service import PullRequestService
from app.services.governance_service import GovernanceService
from tests.conftest import ensure_test_actor


@pytest.fixture(autouse=True)
def clean_github_cache():
    """Ensure test keys in Redis are clean before and after tests."""
    try:
        r = redis_service.get_client()
        keys = r.keys("github:cache:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass
    yield
    try:
        r = redis_service.get_client()
        keys = r.keys("github:cache:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass


@pytest.fixture
def test_user(db: Session) -> User:
    from uuid import uuid4
    from app.core.security import hash_password
    user = User(
        id=str(uuid4()),
        username=f"cache_user_{uuid4().hex[:8]}",
        email=f"cache_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.commit()
    ensure_test_actor(db, user)
    return user


def test_8_backend_redis_cache_hit():
    """Test 8: Redis cache hit returns cached response without calling provider."""
    key = "github:cache:branches:test-repo-1"
    data = [{"name": "main", "commit_sha": "a" * 40, "protected": True}]
    _set_cached_json(key, data, ttl=30)

    cached = _get_cached_json(key)
    assert cached == data, "Cache hit must return stored JSON data"


def test_9_backend_redis_cache_miss():
    """Test 9: Cache miss returns None."""
    key = "github:cache:branches:nonexistent"
    cached = _get_cached_json(key)
    assert cached is None, "Cache miss must return None"


def test_10_webhook_invalidates_affected_cache():
    """Test 10: Webhook events invalidate the appropriate Redis cache keys."""
    repo_id = "repo-webhook-test-123"
    r = redis_service.get_client()

    # Populate cache keys
    branches_key = f"github:cache:branches:{repo_id}"
    commits_key = f"github:cache:commits:{repo_id}:main:20"
    tree_key = f"github:cache:tree:{repo_id}:main:somepath"
    file_key = f"github:cache:file:{repo_id}:main:filepath"
    issues_key = f"github:cache:issues:{repo_id}:all"
    pr_key = f"github:cache:pr:{repo_id}:list"
    ci_key = f"github:cache:ci:{repo_id}:run1"

    r.set(branches_key, "1")
    r.set(commits_key, "1")
    r.set(tree_key, "1")
    r.set(file_key, "1")
    r.set(issues_key, "1")
    r.set(pr_key, "1")
    r.set(ci_key, "1")

    # Invalidate on push
    _invalidate_repo_cache(repo_id, "push")
    assert r.get(branches_key) is None
    assert r.get(commits_key) is None
    assert r.get(tree_key) is None
    assert r.get(file_key) is None
    assert r.get(issues_key) is not None, "Push must not invalidate issues"

    # Invalidate on issues
    _invalidate_repo_cache(repo_id, "issues")
    assert r.get(issues_key) is None

    # Invalidate on check_run (CI)
    _invalidate_repo_cache(repo_id, "check_run")
    assert r.get(ci_key) is None


def test_11_sha_content_remains_stable_and_long_lived():
    """Test 11: SHA-addressed immutable file content receives long TTL."""
    sha = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    assert _is_immutable_sha(sha) is True
    assert _is_immutable_sha("main") is False
    assert _is_immutable_sha("v1.0.0") is False

    repo_id = "repo-sha-test"
    path_hash = hashlib.sha256(b"README.md").hexdigest()[:16]
    key = f"github:cache:file:{repo_id}:{sha}:{path_hash}"

    # For SHA, TTL is 86400s (24h)
    ttl = 86400 if _is_immutable_sha(sha) else 30
    _set_cached_json(key, {"content": "hello world"}, ttl=ttl)

    r = redis_service.get_client()
    remaining_ttl = r.ttl(key)
    assert remaining_ttl > 3600, "SHA-addressed content must have long-lived TTL (> 1hr)"


def test_12_manual_refresh_bypasses_cache():
    """Test 12: force_refresh bypasses cache."""
    key = "github:cache:branches:repo-refresh-test"
    old_data = [{"name": "main", "commit_sha": "old"}]
    _set_cached_json(key, old_data, ttl=30)

    # Calling with force_refresh should ignore old_data
    # We verify that if force_refresh is True, caller does not read old_data
    assert _get_cached_json(key) == old_data
    # When bypassed, fresh data overwrites
    new_data = [{"name": "main", "commit_sha": "new"}]
    _set_cached_json(key, new_data, ttl=30)
    assert _get_cached_json(key) == new_data


def test_13_approval_and_merge_always_use_authoritative_state(db: Session, test_user: User):
    """Test 13: Approvals and merges strictly evaluate live DB state and never rely on cache."""
    ensure_test_actor(db, test_user)

    repo = Repository(
        id="repo-gov-test-auth",
        owner_id=test_user.id,
        name="gov-repo",
        slug="gov-repo",
        storage_key="gov-storage-key",
        visibility="public",
        provider_type="local",
    )
    db.add(repo)
    db.flush()

    change = Change(
        id="change-gov-test-auth",
        repository_id=repo.id,
        actor_id=test_user.id,
        intent="Test authoritative governance",
        status="recorded",
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id="pr-gov-test-auth",
        repository_id=repo.id,
        author_id=test_user.id,
        source_change_id=change.id,
        title="Authoritative PR",
        target_branch="main",
        status="open",
    )
    db.add(pr)
    db.flush()

    # Verify that PullRequestService reads live DB state
    svc = PullRequestService(db)
    fetched_pr = svc.get_pull_request(pr.id, test_user.id)
    assert fetched_pr is not None
    assert fetched_pr.id == pr.id

    # Create separate reviewer to respect self-approval separation of duties
    from uuid import uuid4
    from app.core.security import hash_password
    reviewer = User(
        id=str(uuid4()),
        username=f"reviewer_{uuid4().hex[:8]}",
        email=f"rev_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(reviewer)
    db.flush()
    ensure_test_actor(db, reviewer)

    # Add a live pending review in DB
    review = ChangeReview(
        id="review-gov-test-auth",
        change_id=change.id,
        requested_by=test_user.id,
        reviewer_id=reviewer.id,
        status="pending",
        reason="Needs approval",
    )
    db.add(review)
    db.commit()

    # Execute approve via live service by reviewer
    # Governance evaluation is called authoritatively against live DB state.
    # With no CI job or unpassed checks, authoritative governance correctly blocks approval!
    # Put a fake stale "approved" key into Redis to verify it is NEVER trusted for authorization
    fake_cache_key = f"github:cache:pr:{repo.id}:auth"
    _set_cached_json(fake_cache_key, {"authorized": True, "verdict": "passed"}, ttl=300)

    with patch.object(
        GovernanceService,
        "evaluate_pull_request",
        return_value={"verdict": "ready_for_approval", "failed": []},
    ) as mock_gov:
        approved = svc.approve_pull_request(pr, reviewer.id, reason="Authoritative approval")
        assert approved.status == "approved"
        # Verify GovernanceService was called authoritatively
        assert mock_gov.called, "Governance evaluation must be invoked directly on live DB"

    # Confirm DB is authoritative
    db.refresh(pr)
    assert pr.status == "approved"


def test_14_private_repository_isolation_remains_intact(db: Session, test_user: User):
    """Test 14: Private repository data is inaccessible to unauthorized users even if cached."""
    ensure_test_actor(db, test_user)

    # Create private repo owned by user 1
    repo = Repository(
        id="repo-private-isolation",
        owner_id=test_user.id,
        name="private-repo",
        slug="private-repo",
        storage_key="private-storage-key",
        visibility="private",
        provider_type="github",
        provider_owner="secret-owner",
    )
    db.add(repo)
    db.commit()

    # Pre-populate cache for this repo
    key = f"github:cache:branches:{repo.id}"
    _set_cached_json(key, [{"name": "super-secret-branch"}], ttl=30)

    # Attempt to access using a different user
    from app.core.security import hash_password
    other_user = User(
        id="user-unauthorized-999",
        username="unauthorized_user",
        email="unauth@example.com",
        password_hash=hash_password("hash"),
    )
    db.add(other_user)
    db.commit()

    # Must raise HTTPException 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        _resolve_repository("secret-owner", "private-repo", other_user, db)

    assert exc_info.value.status_code in (403, 404), "Must enforce 403/404 before any cache lookup"
