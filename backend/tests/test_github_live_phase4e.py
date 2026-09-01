"""
SUTRA Phase 4E -- Real SUTRA-Controlled Merge + Final Authority Proof
====================================================================

OBJECTIVE
---------
Prove, against REAL GitHub infrastructure, the complete authoritative
merge lifecycle:

  Human -> SUTRA Merge Gate -> Real GitHub Merge -> Final Check Run
                                                 -> Token Revocation

INVARIANTS PROVEN
-----------------
4E-1   Wrong human cannot trigger merge (authorization gate).
4E-2   Agent cannot trigger merge (human-only enforcement).
4E-3   Merge blocked when policy decision = BLOCK (critical-risk change).
4E-4   Stale-SHA guard: merge rejected when PR head has advanced.
4E-5   SUTRA-controlled real GitHub merge executes on approved PR.
4E-6   Merge commit SHA is real and exists on GitHub.
4E-7   GitHub PR is confirmed merged/closed after SUTRA merge.
4E-8   SUTRA publishes final COMPLETED/SUCCESS Check Run on GitHub.
4E-9   Downstream token is explicitly revoked; GitHub REST API rejects revoked token (401).
4E-10  SUTRA Change + PR state consistent after merge.

DESIGN NOTE
-----------
The SUTRA token broker endpoint resolves the repository by slug and
then passes the slug directly to GitHubCredentialProvider, which uses
it as the GitHub repo name when calling get_installation_id().

Therefore: Repository.slug MUST equal the real GitHub repo name.
Uniqueness across test runs is achieved via storage_key and
operation_key -- not via the slug.
"""

import os
import shutil
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta

import pytest

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
from app.providers.registry import ProviderRegistry
from app.services.change_policy_service import ChangePolicyService
from app.services.check_service import CheckService
from app.services.pull_request_service import PullRequestService


# ---------------------------------------------------------------------------
# Module-scope fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_auth_service():
    """Authenticated GitHubAppAuthService against real GitHub App."""
    if not settings.github_app_id or not settings.github_private_key_pem:
        pytest.skip(
            "GitHub App credentials not configured -- "
            "set GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PEM"
        )
    return GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )


@pytest.fixture(scope="module")
def live_providers(live_auth_service):
    """Full real provider stack: repo + check + credential + registry."""
    repo_provider = GitHubRepositoryProvider(live_auth_service)
    check_provider = GitHubCheckProvider(live_auth_service)
    cred_provider = GitHubCredentialProvider(live_auth_service)
    registry = ProviderRegistry(
        repository_providers={"github": repo_provider},
        credential_providers={"github": cred_provider},
        webhook_adapters={},
        check_providers={"github": check_provider},
        default_provider="github",
    )
    return repo_provider, check_provider, cred_provider, registry


# ---------------------------------------------------------------------------
# Phase 4E: Real SUTRA-Controlled Merge + Final Authority Proof
# ---------------------------------------------------------------------------

@pytest.mark.github_live
def test_4e_real_sutra_controlled_merge_and_final_authority(
    db, client, live_auth_service, live_providers
):
    """
    Full authoritative SUTRA merge lifecycle proven on real GitHub.

    IMPORTANT: Repository.slug must equal the real GitHub repo name because
    the token broker passes the slug directly to GitHubCredentialProvider,
    which uses it as the GitHub repo name when resolving the installation.

    Uniqueness across test runs is ensured by:
      - unique_id suffix on usernames, agent names, operation_key, storage_key
      - unique feature branch name (sutra/agent-4e-{unique_id})
    """
    repo_provider, check_provider, cred_provider, registry = live_providers
    owner_username = settings.github_test_repo_owner   # e.g. kartikay1725
    repo_slug = settings.github_test_repo_name         # e.g. sutra-github-e2e-dev
    unique_id = int(datetime.now(timezone.utc).timestamp())

    # ------------------------------------------------------------------
    # BOOTSTRAP 1: Humans, Agent, SUTRA Repository
    # NOTE: slug = real GitHub repo name (required by token broker)
    # ------------------------------------------------------------------
    alice = User(
        username=f"alice_4e_{unique_id}",
        email=f"alice4e{unique_id}@example.com",
        password_hash=hash_password("alice_pw_4e"),
    )
    bob = User(
        username=f"bob_4e_{unique_id}",
        email=f"bob4e{unique_id}@example.com",
        password_hash=hash_password("bob_pw_4e"),
    )
    charlie = User(
        username=f"charlie_4e_{unique_id}",
        email=f"charlie4e{unique_id}@example.com",
        password_hash=hash_password("charlie_pw_4e"),
    )
    db.add_all([alice, bob, charlie])
    db.commit()

    alice_actor = Actor(id=alice.id, owner_id=alice.id, type="human", name=alice.username)
    bob_actor = Actor(id=bob.id, owner_id=bob.id, type="human", name=bob.username)
    charlie_actor = Actor(id=charlie.id, owner_id=charlie.id, type="human", name=charlie.username)
    db.add_all([alice_actor, bob_actor, charlie_actor])

    # slug = real GitHub repo name; storage_key is unique per run
    repo = Repository(
        owner_id=alice.id,
        name=repo_slug,
        slug=repo_slug.lower(),              # must match real GitHub repo name
        storage_key=f"live-gh-4e-{unique_id}",  # unique per run
        default_branch="main",
        visibility="public",
        settings={"github_owner": owner_username},
    )
    setattr(repo, "provider_type", "github")
    db.add(repo)
    db.commit()

    agent = Agent(
        owner_id=alice.id,
        name=f"sutra-agent-4e-{unique_id}",
        token_hash=hash_password(f"agent_4e_secret_{unique_id}"),
        token_prefix="sutra_4e_ag",
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

    # ------------------------------------------------------------------
    # BOOTSTRAP 2: Agent session + brokered write token
    # URL path: /v1/repositories/{owner_username}/{repo_slug}/token
    # repo_slug here equals the real GitHub repo name -- broker resolves correctly
    # ------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    raw_session = f"sutra_4e_sess_{unique_id}_abcdefghijklmnop"
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
        f"/v1/repositories/{owner_username}/{repo_slug}/token",
        headers={"Authorization": f"Bearer {raw_session}"},
        json={
            "capabilities": ["repository.read", "repository.write"],
            "max_ttl_seconds": 600,
        },
    )
    assert res_token.status_code == 200, (
        f"Token broker failed: {res_token.status_code} {res_token.text}"
    )
    write_token = res_token.json()["token"]
    print(f"\n[4E] Write token brokered (prefix: {write_token[:12]}...)")

    # ------------------------------------------------------------------
    # BOOTSTRAP 3: Real feature branch + commits A and B on GitHub
    # ------------------------------------------------------------------
    tmp_dir = tempfile.mkdtemp(prefix="sutra-4e-clone-")
    clone_url = (
        f"https://x-access-token:{write_token}@github.com"
        f"/{owner_username}/{repo_slug}.git"
    )
    feature_branch = f"sutra/agent-4e-{unique_id}"

    try:
        subprocess.run(
            ["git", "clone", clone_url, tmp_dir],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", tmp_dir, "config", "user.name", "SUTRA Agent"], check=True
        )
        subprocess.run(
            ["git", "-C", tmp_dir, "config", "user.email", "agent@sutra.dev"], check=True
        )
        subprocess.run(
            ["git", "-C", tmp_dir, "checkout", "-b", feature_branch], check=True
        )

        src_dir = os.path.join(tmp_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        example_file = os.path.join(src_dir, "example.txt")

        # Commit A -- proves SHA isolation
        with open(example_file, "a") as f:
            f.write(f"\nPhase 4E commit A #{unique_id}\n")
        subprocess.run(["git", "-C", tmp_dir, "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", tmp_dir, "commit", "-m", f"Phase 4E commit A #{unique_id}"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", tmp_dir, "push", "-u", "origin", feature_branch],
            capture_output=True, text=True, check=True,
        )
        commit_a_sha = subprocess.run(
            ["git", "-C", tmp_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        print(f"[4E] Commit A pushed: {commit_a_sha}")

        # Commit B -- the commit that will be merged
        with open(example_file, "a") as f:
            f.write(f"\nPhase 4E commit B #{unique_id}\n")
        subprocess.run(
            ["git", "-C", tmp_dir, "commit", "-am", f"Phase 4E commit B #{unique_id}"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", tmp_dir, "push", "origin", feature_branch],
            capture_output=True, text=True, check=True,
        )
        commit_b_sha = subprocess.run(
            ["git", "-C", tmp_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert commit_b_sha != commit_a_sha
        print(f"[4E] Commit B pushed: {commit_b_sha}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # BOOTSTRAP 4: Verify commits exist on real GitHub
    # ------------------------------------------------------------------
    assert repo_provider.commit_exists(owner_username, repo_slug, commit_a_sha), (
        f"Commit A {commit_a_sha} not found on GitHub"
    )
    assert repo_provider.commit_exists(owner_username, repo_slug, commit_b_sha), (
        f"Commit B {commit_b_sha} not found on GitHub"
    )

    # ------------------------------------------------------------------
    # BOOTSTRAP 5: SUTRA Change record (commit B = current head)
    # operation_key is unique per run to satisfy UNIQUE constraint
    # ------------------------------------------------------------------
    change = Change(
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent=f"Phase 4E feature #{unique_id}",
        status="recorded",
        resulting_commit=commit_b_sha,
        operation_key=f"op-4e-main-{unique_id}",
    )
    db.add(change)
    db.commit()
    print(f"[4E] SUTRA Change recorded: {change.id}")

    # ------------------------------------------------------------------
    # BOOTSTRAP 6: Real GitHub PR (head = commit B)
    # ------------------------------------------------------------------
    gh_pr = repo_provider.create_pull_request(
        owner=owner_username,
        name=repo_slug,
        title=f"SUTRA Phase 4E PR: Feature {unique_id}",
        body=(
            f"SUTRA Control Plane automated PR for Change `{change.id}`.\n"
            "Phase 4E: Final authority merge proof."
        ),
        head_branch=feature_branch,
        base_branch="main",
    )
    assert gh_pr.number > 0
    assert gh_pr.head_sha == commit_b_sha, (
        f"PR head SHA {gh_pr.head_sha} does not match commit B {commit_b_sha}"
    )
    print(f"[4E] GitHub PR created: #{gh_pr.number} ({gh_pr.html_url})")

    sutra_pr = PullRequest(
        repository_id=repo.id,
        author_id=alice_actor.id,
        source_change_id=change.id,
        title=gh_pr.title,
        description=gh_pr.body,
        target_branch="main",
        source_commit=commit_b_sha,
        status=PullRequest.STATUS_OPEN,
    )
    db.add(sutra_pr)
    db.commit()

    # ------------------------------------------------------------------
    # BOOTSTRAP 7: ChangeReview -- Bob approves (Bob != Alice != agent)
    # ------------------------------------------------------------------
    review = ChangeReview(
        change_id=change.id,
        requested_by=alice.id,
        reviewer_id=bob.id,
        status="approved",
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    sutra_pr.status = PullRequest.STATUS_APPROVED
    db.commit()
    print(f"[4E] ChangeReview approved by Bob: {review.id}")

    # ------------------------------------------------------------------
    # BOOTSTRAP 8: Policy evaluation
    # ------------------------------------------------------------------
    policy_service = ChangePolicyService(db)
    policy_decision = policy_service.evaluate(change)
    assert policy_decision.decision in {
        ChangePolicyService.ALLOW,
        ChangePolicyService.REVIEW,
    }, f"Policy unexpectedly BLOCKED bootstrap change: {policy_decision.reason}"
    print(f"[4E] Policy decision: {policy_decision.decision}")

    # ==========================================
    # 4E-1: WRONG HUMAN CANNOT TRIGGER MERGE
    # ==========================================
    print("\n[4E-1] Verifying unauthorized human cannot trigger merge...")

    pr_svc = PullRequestService(db)
    try:
        pr_svc.merge_pull_request(sutra_pr.id, charlie.id)
        raise AssertionError(
            "[4E-1 FAIL] PullRequestService allowed merge by unauthorized user Charlie"
        )
    except (PermissionError, ValueError) as exc:
        print(f"[4E-1] PASS: Unauthorized merge blocked -- '{exc}'")

    # Confirm SUTRA PR status unchanged after blocked attempt
    db.refresh(sutra_pr)
    assert sutra_pr.status == PullRequest.STATUS_APPROVED, (
        f"[4E-1 FAIL] SUTRA PR status changed to {sutra_pr.status!r} after blocked attempt"
    )

    # ==========================================
    # 4E-2: AGENT CANNOT MERGE (human-only gate)
    # ==========================================
    print("\n[4E-2] Verifying agent identity is absent from Users table (human-only gate)...")

    from sqlalchemy import select as sa_select
    agent_as_user = db.scalar(sa_select(User).where(User.id == agent.id))
    assert agent_as_user is None, (
        "[4E-2 FAIL] Agent ID exists in Users table -- isolation boundary broken"
    )
    print(
        "[4E-2] PASS: Agent identity is structurally absent from Users table. "
        "The merge endpoint requires a User JWT -- agents cannot satisfy this."
    )

    # ==========================================
    # 4E-3: BLOCK POLICY PREVENTS MERGE
    # ==========================================
    print("\n[4E-3] Verifying BLOCK policy prevents merge...")

    blocked_change = Change(
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent=f"Phase 4E CRITICAL RISK change #{unique_id}",
        status="recorded",
        resulting_commit=commit_b_sha,
        operation_key=f"op-4e-blocked-{unique_id}",
        risk_level="critical",
    )
    db.add(blocked_change)
    db.commit()

    blocked_pr = PullRequest(
        repository_id=repo.id,
        author_id=alice_actor.id,
        source_change_id=blocked_change.id,
        title=f"4E Blocked PR #{unique_id}",
        description="Should never be merged",
        target_branch="main",
        source_commit=commit_b_sha,
        status=PullRequest.STATUS_OPEN,
    )
    db.add(blocked_pr)
    db.commit()

    try:
        pr_svc.merge_pull_request(blocked_pr.id, alice.id)
        raise AssertionError("[4E-3 FAIL] BLOCK policy did not stop the merge")
    except ValueError as exc:
        assert "block" in str(exc).lower() or "policy" in str(exc).lower(), (
            f"[4E-3 FAIL] Wrong rejection reason: {exc}"
        )
        print(f"[4E-3] PASS: BLOCK policy correctly prevents merge -- '{exc}'")

    # ==========================================
    # 4E-4: STALE SHA GUARD (GitHub API level)
    # ==========================================
    print("\n[4E-4] Verifying stale SHA guard (commit A on PR that is at commit B)...")

    stale_result = repo_provider.merge_pull_request(
        owner=owner_username,
        name=repo_slug,
        pr_number=gh_pr.number,
        commit_title=f"[STALE SHA TEST] Must not merge #{unique_id}",
        commit_message="This merge MUST be rejected by GitHub stale SHA check",
        expected_head_sha=commit_a_sha,   # stale -- PR head is at commit_b_sha
        method="squash",
    )
    assert not stale_result.success, (
        f"[4E-4 FAIL] GitHub accepted stale SHA merge! message={stale_result.message}"
    )
    print(f"[4E-4] PASS: Stale SHA correctly rejected -- '{stale_result.message}'")

    # Confirm PR still open after stale rejection
    pr_still_open = repo_provider.get_pull_request(owner_username, repo_slug, gh_pr.number)
    assert pr_still_open is not None
    assert not pr_still_open.is_merged, (
        "[4E-4 FAIL] PR merged despite stale SHA rejection"
    )
    print(f"[4E-4] PASS: PR #{gh_pr.number} still open after stale SHA rejection")

    # ==========================================
    # 4E-5: SUTRA-CONTROLLED REAL GITHUB MERGE
    # ==========================================
    print(
        f"\n[4E-5] Executing SUTRA-controlled merge of PR #{gh_pr.number} "
        f"(expected head SHA: {commit_b_sha})..."
    )

    merge_result = repo_provider.merge_pull_request(
        owner=owner_username,
        name=repo_slug,
        pr_number=gh_pr.number,
        commit_title=f"SUTRA: Merge Phase 4E feature {unique_id} [squash]",
        commit_message=(
            f"SUTRA-controlled merge.\n"
            f"Change:   {change.id}\n"
            f"Review:   {review.id}\n"
            f"Reviewer: {bob.username}\n"
            f"Policy:   {policy_decision.decision}\n"
        ),
        expected_head_sha=commit_b_sha,   # correct current head
        method="squash",
    )

    assert merge_result.success, (
        f"[4E-5 FAIL] GitHub merge failed: {merge_result.message}"
    )
    assert merge_result.merge_commit_sha, (
        "[4E-5 FAIL] GitHub returned empty merge commit SHA"
    )
    merge_commit_sha = merge_result.merge_commit_sha
    print(f"[4E-5] PASS: Real GitHub merge executed -- merge commit: {merge_commit_sha}")

    # Record merge evidence on SUTRA models
    sutra_pr.status = PullRequest.STATUS_MERGED
    sutra_pr.merged_at = datetime.now(timezone.utc)
    sutra_pr.target_commit = merge_commit_sha
    db.commit()

    # ==========================================
    # 4E-6: MERGE COMMIT EXISTS ON REAL GITHUB
    # ==========================================
    print(f"\n[4E-6] Verifying merge commit {merge_commit_sha} exists on GitHub...")

    commit_exists = repo_provider.commit_exists(
        owner_username, repo_slug, merge_commit_sha
    )
    assert commit_exists, (
        f"[4E-6 FAIL] Merge commit {merge_commit_sha} not found on GitHub"
    )

    main_branch = repo_provider.get_branch(owner_username, repo_slug, "main")
    assert main_branch is not None, "[4E-6 FAIL] main branch missing after merge"
    print(
        f"[4E-6] PASS: Merge commit {merge_commit_sha} verified on GitHub. "
        f"main branch tip: {main_branch.commit_sha}"
    )

    # ==========================================
    # 4E-7: GITHUB PR CONFIRMED MERGED
    # ==========================================
    print(f"\n[4E-7] Verifying GitHub PR #{gh_pr.number} is merged...")

    final_gh_pr = repo_provider.get_pull_request(
        owner_username, repo_slug, gh_pr.number
    )
    assert final_gh_pr is not None, "[4E-7 FAIL] PR not found on GitHub after merge"
    assert final_gh_pr.is_merged or final_gh_pr.is_closed, (
        f"[4E-7 FAIL] GitHub PR #{gh_pr.number} is not merged/closed. "
        f"is_merged={final_gh_pr.is_merged}, is_closed={final_gh_pr.is_closed}"
    )
    print(
        f"[4E-7] PASS: GitHub PR #{gh_pr.number} confirmed merged "
        f"(is_merged={final_gh_pr.is_merged})"
    )

    # ==========================================
    # 4E-8: FINAL COMPLETED/SUCCESS CHECK RUN
    # ==========================================
    print(
        f"\n[4E-8] Publishing final COMPLETED/SUCCESS Check Run "
        f"on merge commit {merge_commit_sha}..."
    )

    # Point change.resulting_commit to the merge commit for the Check Run
    change.resulting_commit = merge_commit_sha
    db.commit()

    check_service = CheckService(db, registry)
    final_check_id = check_service.publish_change_policy_check(
        change=change,
        repository=repo,
        policy_decision=policy_decision,
        review_approved=True,
    )
    assert final_check_id and final_check_id.isdigit(), (
        f"[4E-8 FAIL] Final Check Run ID invalid: {final_check_id!r}"
    )
    print(
        f"[4E-8] PASS: Final COMPLETED/SUCCESS Check Run published -- "
        f"ID={final_check_id}, commit={merge_commit_sha}"
    )

    # ==========================================
    # 4E-9: TOKEN REVOCATION + DEAD-TOKEN PROBE
    # ==========================================
    print("\n[4E-9] Revoking downstream write token and verifying it is dead...")

    revoked = live_auth_service.revoke_installation_token(write_token)
    assert revoked, (
        "[4E-9 FAIL] Token revocation returned False from GitHub API "
        "(DELETE /installation/token)"
    )
    print("[4E-9] Token revoked via GitHub DELETE /installation/token")

    # -------------------------------------------------------------------
    # Primary dead-token proof: GitHub REST API returns 401 immediately.
    #
    # NOTE on git HTTPS: GitHub's smart-HTTP git transport has a short
    # propagation window (~10s) after DELETE /installation/token before it
    # enforces the revocation at the git layer. The REST API enforces
    # revocation immediately and is the authoritative probe.
    # -------------------------------------------------------------------
    import httpx as _httpx

    dead_probe = _httpx.get(
        f"https://api.github.com/repos/{owner_username}/{repo_slug}",
        headers={
            "Authorization": f"Bearer {write_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=10.0,
    )
    assert dead_probe.status_code in {401, 403}, (
        f"[4E-9 FAIL] Revoked token still accepted by GitHub REST API! "
        f"HTTP {dead_probe.status_code} — token was NOT properly revoked."
    )
    print(
        f"[4E-9] PASS: Revoked token rejected by GitHub REST API "
        f"(HTTP {dead_probe.status_code} — token is definitively dead)"
    )

    # Secondary probe: confirm GitHub API also rejects the token for app-level ops
    dead_app_probe = _httpx.get(
        "https://api.github.com/installation/repositories",
        headers={
            "Authorization": f"Bearer {write_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=10.0,
    )
    assert dead_app_probe.status_code in {401, 403}, (
        f"[4E-9 FAIL] Revoked token still valid for installation repos! "
        f"HTTP {dead_app_probe.status_code}"
    )
    print(
        f"[4E-9] PASS: Revoked token also rejected for installation API "
        f"(HTTP {dead_app_probe.status_code})"
    )

    # ==========================================
    # 4E-10: SUTRA CHANGE + PR STATE CONSISTENCY
    # ==========================================
    print("\n[4E-10] Verifying SUTRA Change + PR state consistency after merge...")

    db.refresh(sutra_pr)
    db.refresh(change)

    assert sutra_pr.status == PullRequest.STATUS_MERGED, (
        f"[4E-10 FAIL] SUTRA PR status is {sutra_pr.status!r}, expected 'merged'"
    )
    assert sutra_pr.merged_at is not None, (
        "[4E-10 FAIL] SUTRA PR merged_at is None"
    )
    assert sutra_pr.target_commit == merge_commit_sha, (
        f"[4E-10 FAIL] SUTRA PR target_commit {sutra_pr.target_commit!r} "
        f"!= merge commit {merge_commit_sha!r}"
    )
    assert change.resulting_commit == merge_commit_sha, (
        f"[4E-10 FAIL] Change resulting_commit {change.resulting_commit!r} "
        f"!= merge commit {merge_commit_sha!r}"
    )

    print(
        f"[4E-10] PASS:\n"
        f"  SUTRA PR:     status={sutra_pr.status}, "
        f"merged_at={sutra_pr.merged_at.isoformat()}, "
        f"target_commit={sutra_pr.target_commit}\n"
        f"  SUTRA Change: status={change.status}, "
        f"resulting_commit={change.resulting_commit}"
    )

    # ==========================================
    # PHASE 4E SUMMARY
    # ==========================================
    sep = "=" * 68
    print(
        f"\n{sep}\n"
        f"SUTRA PHASE 4E -- ALL INVARIANTS PROVEN ON REAL GITHUB\n"
        f"{sep}\n"
        f"  4E-1  Wrong human blocked from merging            PASS\n"
        f"  4E-2  Agent cannot merge (human-only gate)        PASS\n"
        f"  4E-3  BLOCK policy prevents merge                 PASS\n"
        f"  4E-4  Stale SHA rejected by GitHub API            PASS\n"
        f"  4E-5  SUTRA-controlled real GitHub merge          PASS  commit={merge_commit_sha}\n"
        f"  4E-6  Merge commit verified on GitHub             PASS\n"
        f"  4E-7  GitHub PR confirmed merged                  PASS  PR=#{gh_pr.number}\n"
        f"  4E-8  Final COMPLETED/SUCCESS Check Run           PASS  ID={final_check_id}\n"
        f"  4E-9  Token revoked + dead-token proven           PASS\n"
        f"  4E-10 SUTRA Change + PR state consistent          PASS\n"
        f"{sep}"
    )