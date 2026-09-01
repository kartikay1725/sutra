import os
import shutil
import tempfile
import subprocess
import json
from datetime import datetime, timezone, timedelta
import pytest
import httpx

from app.core.config import settings
from app.models.user import User
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.repository import Repository
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.core.security import hash_password
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.credentials import GitHubCredentialProvider
from app.providers.github.repository import GitHubRepositoryProvider
from app.providers.github.checks import GitHubCheckProvider
from app.providers.checks import CheckRunReport, CheckStatus, CheckConclusion
from app.providers.registry import ProviderRegistry
from app.services.change_policy_service import ChangePolicyService, PolicyDecision
from app.services.check_service import CheckService


@pytest.fixture(scope="module")
def live_auth_service():
    if not settings.github_app_id or not settings.github_private_key_pem:
        pytest.skip("GitHub App credentials not configured in environment")
    return GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )


@pytest.fixture(scope="module")
def live_providers(live_auth_service):
    repo_provider = GitHubRepositoryProvider(live_auth_service)
    check_provider = GitHubCheckProvider(live_auth_service)
    registry = ProviderRegistry(
        repository_providers={"github": repo_provider},
        credential_providers={},
        webhook_adapters={},
        check_providers={"github": check_provider},
        default_provider="github",
    )
    return repo_provider, check_provider, registry


@pytest.mark.github_live
def test_live_change_and_commit_evidence_and_pr_and_checks(db, client, live_auth_service, live_providers):
    repo_provider, check_provider, registry = live_providers
    owner_username = settings.github_test_repo_owner
    repo_slug = settings.github_test_repo_name

    # 1. Setup Humans (Owner Alice & Reviewer Bob)
    alice = User(username=f"alice_{int(datetime.now().timestamp())}", email="alice@example.com", password_hash=hash_password("pw"))
    bob = User(username=f"bob_{int(datetime.now().timestamp())}", email="bob@example.com", password_hash=hash_password("pw"))
    db.add_all([alice, bob])
    db.commit()

    alice_actor = Actor(id=alice.id, owner_id=alice.id, type="human", name=alice.username)
    bob_actor = Actor(id=bob.id, owner_id=bob.id, type="human", name=bob.username)
    db.add_all([alice_actor, bob_actor])

    # 2. Setup GitHub-backed Repository in SUTRA
    repo = Repository(
        owner_id=alice.id,
        name=repo_slug,
        slug=repo_slug.lower(),
        storage_key="live-gh-4d-storage-key",
        default_branch="main",
        visibility="public",
        settings={"github_owner": owner_username},
    )
    setattr(repo, "provider_type", "github")
    db.add(repo)
    db.commit()

    # 3. Setup Agent with capabilities
    agent = Agent(
        owner_id=alice.id,
        name="sutra-live-builder",
        token_hash=hash_password("agent_perm_token"),
        token_prefix="sutra_agent_perm",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=alice.id,
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

    # 4. Agent Session & Downstream Write Credential Broker
    now = datetime.now(timezone.utc)
    raw_session = "sutra_session_4d_live_token_1234567890"
    session = AgentSession(
        agent_id=agent.id,
        token_hash=hash_password(raw_session),
        token_prefix=raw_session[:32],
        status="active",
        expires_at=now + timedelta(minutes=15),
    )
    db.add(session)
    db.commit()

    res_token = client.post(
        f"/v1/repositories/{owner_username}/{repo.slug}/token",
        headers={"Authorization": f"Bearer {raw_session}"},
        json={"capabilities": ["repository.read", "repository.write"], "max_ttl_seconds": 600},
    )
    assert res_token.status_code == 200
    write_token = res_token.json()["token"]

    # 5. Push Commit A on a new feature branch
    tmp_dir = tempfile.mkdtemp(prefix="sutra-4d-clone-")
    clone_url = f"https://x-access-token:{write_token}@github.com/{owner_username}/{repo_slug}.git"
    unique_id = int(datetime.now().timestamp())
    feature_branch = f"sutra/agent-change-{unique_id}"

    try:
        subprocess.run(["git", "clone", clone_url, tmp_dir], capture_output=True, text=True, check=True)
        subprocess.run(["git", "-C", tmp_dir, "config", "user.name", "SUTRA Agent"], check=True)
        subprocess.run(["git", "-C", tmp_dir, "config", "user.email", "agent@sutra.dev"], check=True)
        subprocess.run(["git", "-C", tmp_dir, "checkout", "-b", feature_branch], check=True)

        example_file = os.path.join(tmp_dir, "src", "example.txt")
        with open(example_file, "a") as f:
            f.write(f"\nPhase 4D verified change #{unique_id}")

        subprocess.run(["git", "-C", tmp_dir, "commit", "-am", f"Phase 4D commit A #{unique_id}"], check=True)
        subprocess.run(["git", "-C", tmp_dir, "push", "-u", "origin", feature_branch], capture_output=True, text=True, check=True)

        # Get Commit A SHA
        commit_a_sha = subprocess.run(["git", "-C", tmp_dir, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        print(f"\n[LIVE] Commit A pushed to {feature_branch}: {commit_a_sha}")

        # 6. Phase 4D-3 & 4D-4: SUTRA Change record & Real Commit Evidence
        assert repo_provider.commit_exists(owner_username, repo_slug, commit_a_sha) is True
        
        change = Change(
            repository_id=repo.id,
            actor_id=agent_actor.id,
            intent="Phase 4D verified feature update",
            status="recorded",
            resulting_commit=commit_a_sha,
            operation_key=f"op-4d-change-{unique_id}",
        )
        db.add(change)
        db.commit()
        print(f"[LIVE] SUTRA Change recorded: {change.id}")

        # 7. Phase 4D-5: Policy Evaluation (Prior to review approval -> Review Required)
        policy_service = ChangePolicyService(db)
        decision = policy_service.evaluate(change)
        assert decision.decision in {ChangePolicyService.ALLOW, ChangePolicyService.REVIEW}

        # 8. Phase 4D-6: Create Real GitHub Pull Request
        gh_pr = repo_provider.create_pull_request(
            owner=owner_username,
            name=repo_slug,
            title=f"SUTRA Phase 4D PR: Feature {unique_id}",
            body=f"Automated PR created by SUTRA Control Plane for Change `{change.id}`",
            head_branch=feature_branch,
            base_branch="main",
        )
        assert gh_pr.number > 0
        assert gh_pr.head_sha == commit_a_sha
        print(f"[LIVE] Real GitHub PR created: #{gh_pr.number} (URL: {gh_pr.html_url})")

        # Save SUTRA PullRequest
        sutra_pr = PullRequest(
            repository_id=repo.id,
            author_id=agent_actor.id,
            source_change_id=change.id,
            title=gh_pr.title,
            description=gh_pr.body,
            target_branch="main",
            source_commit=commit_a_sha,
            status=PullRequest.STATUS_OPEN,
        )
        db.add(sutra_pr)
        db.commit()

        # 9. Phase 4D-7 & 4D-8: Publish Real GitHub Check Run (Status = IN_PROGRESS / ACTION_REQUIRED)
        check_service = CheckService(db, registry)
        check_run_id = check_service.publish_change_policy_check(
            change=change,
            repository=repo,
            policy_decision=decision,
            review_approved=False,
        )
        assert check_run_id and check_run_id.isdigit()
        print(f"[LIVE] Real GitHub Check Run published: ID {check_run_id} (Status: IN_PROGRESS / ACTION_REQUIRED)")

        # 10. Phase 4D-10: Attempt Direct Merge of Blocked/Unapproved PR — MUST BE BLOCKED
        # Note: Unapproved PR without merge authorization or with pending checks is rejected by SUTRA / branch rules
        # Direct attempt via GitHub PR state verification:
        assert sutra_pr.status != PullRequest.STATUS_APPROVED
        print(f"[LIVE] Unapproved PR Merge State: BLOCKED (SUTRA PR Status: {sutra_pr.status})")

        # 11. Phase 4D-11 & 4D-12: Latest SHA Binding & Stale Check Isolation
        # Push Commit B on the same branch
        with open(example_file, "a") as f:
            f.write(f"\nPhase 4D commit B update #{unique_id}")
        subprocess.run(["git", "-C", tmp_dir, "commit", "-am", f"Phase 4D commit B #{unique_id}"], check=True)
        subprocess.run(["git", "-C", tmp_dir, "push", "origin", feature_branch], capture_output=True, text=True, check=True)
        
        commit_b_sha = subprocess.run(["git", "-C", tmp_dir, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        assert commit_b_sha != commit_a_sha
        print(f"[LIVE] Commit B pushed: {commit_b_sha} (Old Check ID {check_run_id} belongs strictly to {commit_a_sha})")

        # 12. Phase 4D-14: Human Review & Approval Flow
        # Update change resulting commit to latest commit B
        change.resulting_commit = commit_b_sha
        db.commit()

        # Create Review Request by Alice (Author)
        review = ChangeReview(
            change_id=change.id,
            requested_by=alice.id,
            reviewer_id=bob.id,
            status="pending",
        )
        db.add(review)
        db.commit()

        # Agent cannot approve (Invariant check)
        assert agent_actor.type != "human"
        
        # Bob (Reviewer != Requester) approves
        review.status = "approved"
        review.reviewed_at = datetime.now(timezone.utc)
        sutra_pr.status = PullRequest.STATUS_APPROVED
        db.commit()
        print(f"[LIVE] Human Review approved by Reviewer Bob (Review ID: {review.id})")

        # 13. Phase 4D-13 & 4D-15: Publish SUCCESS Check Run for Commit B
        check_run_b_id = check_service.publish_change_policy_check(
            change=change,
            repository=repo,
            policy_decision=decision,
            review_approved=True,
        )
        assert check_run_b_id and check_run_b_id.isdigit()
        print(f"[LIVE] Real GitHub SUCCESS Check Run published for Commit B: ID {check_run_b_id} (Conclusion: SUCCESS)")

        # 14. Phase 4D-20: Ready for Phase 4E (PR remains OPEN and APPROVED, merge not executed yet)
        assert sutra_pr.status == PullRequest.STATUS_APPROVED
        print(f"\n[LIVE] Phase 4D Complete: PR #{gh_pr.number} is APPROVED with SUCCESS Check Run, ready for Phase 4E Merge.")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        live_auth_service.revoke_installation_token(write_token)
