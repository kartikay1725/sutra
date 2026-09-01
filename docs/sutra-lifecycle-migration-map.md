# SUTRA Lifecycle Migration Map

**Phase:** 1 — Mapping Only (no code modifications)
**Date:** 2026-08-31
**Source:** Verified against actual source code in backend/app/

This document maps every lifecycle step against the migration decision: what SUTRA owns, what GitHub would own, and what action is required.

---

## How to Read This Document

- **SUTRA-owned:** SUTRA remains the sole authority. No change needed.
- **GitHub-owned:** The current SUTRA implementation will be replaced by a GitHub API call behind a provider adapter.
- **Shared:** Both systems contribute; SUTRA makes decisions, GitHub executes.
- **Keep Current Code:** The current implementation stays as-is (may become the "local provider").
- **Replace With Adapter:** The current implementation moves behind a RepositoryProvider interface; GitHub implementation is added as the first external provider.

---

## Master Lifecycle Step Table

| # | Step | Current Implementation | SUTRA-owned? | GitHub-owned? | Shared? | Keep Current Code? | Replace With Adapter? | Notes |
|---|------|----------------------|:---:|:---:|:---:|:---:|:---:|-------|
| 1 | Human login / JWT | auth.py, dependencies.py, User, UserSession | YES | NO | - | YES | NO | 100% SUTRA. No provider touch. |
| 2 | Agent creation (human) | agents.py, Agent, Actor | YES | NO | - | YES | NO | 100% SUTRA identity. |
| 2a | Agent self-registration | agent_registration.py, AgentRegistrationRequest | YES | NO | - | YES | NO | Device-code-like flow. SUTRA-owned. |
| 3 | Repository access grant | agent_repository_access.py, AgentRepositoryAccess | YES | NO | - | YES | NO | SUTRA authorization — never delegate. |
| 4 | AgentSession creation | agent_dependencies.py, AgentSession | YES | NO | - | YES | NO | 100% SUTRA. Session is SUTRA-issued. |
| 5 | Session heartbeat / validation | agent_dependencies.py, Redis | YES | NO | - | YES | NO | 100% SUTRA. |
| 6 | Repository discovery | repositories.py, Repository table | YES | NO | - | YES | PARTIAL | SUTRA owns the authorization. Provider owns the underlying data when GitHub. Needs adapter. |
| 7 | Repository read (git clone/fetch) | git_http.py -> git http-backend | DECISION | YES | YES | PARTIAL | YES | SUTRA: auth gate. GitHub: actual transport. Local bare repo is current provider. |
| 8 | Repository write (git push) | git_http.py -> git http-backend + pre-receive | DECISION + GATE | YES | YES | PARTIAL | YES | SUTRA: auth + policy gate. GitHub: transport + ref storage. Pre-receive hook has no GitHub equivalent — must become a check run. |
| 9 | Branch creation | Implicit in git push (Step 8) | NO | YES | - | PARTIAL | YES | Local: implicit via git push. GitHub: branch API. SUTRA authorizes, GitHub stores. |
| 10 | Commit creation | Implicit in git push (Step 8) | NO | YES | - | PARTIAL | YES | Local: git object store. GitHub: commit API or push. SUTRA records resulting_commit. |
| 11 | GitPushEvent / change detection | git_push_event_service.py, GitPushEvent | YES | NO | YES | YES | PARTIAL | Event model stays SUTRA-owned. Data source changes: local hook -> GitHub push webhook. |
| 12 | Task assignment / inspection | tasks.py, task_service.py, Task | YES | NO | - | YES | NO | 100% SUTRA. No provider dependency. |
| 13 | Change creation | changes.py, change_service.py, Change | YES | NO | - | YES | NO | 100% SUTRA control-plane record. |
| 14 | Commit evidence recording | changes.py (agent-commit), ChangeFile | YES | NO | - | YES | NO | SUTRA records the SHA. SHA must exist somewhere — local repo or GitHub. |
| 15 | Policy evaluation | change_policy_service.py, ChangePolicyService | YES | NO | - | YES | NO | 100% SUTRA. Must not be delegated. |
| 16 | Conflict detection | conflict_service.py, ConflictService | YES | NO | YES | PARTIAL | YES | SUTRA decides. Local: git merge-base. GitHub: PR mergeable field + merge_commit_sha. Needs adapter. |
| 17 | Pull request creation | pull_requests.py, PullRequestService | SHARED | YES | YES | YES | YES | SUTRA PR record is authoritative. GitHub PR is the substrate. Adapter needed. |
| 18 | PR review / checks | agent_review_service.py, ChangeReview | YES | YES | YES | YES | PARTIAL | SUTRA: review model + approval decision. GitHub: Check Runs to surface policy result. |
| 19 | Human approval | change_reviews.py, ChangeReview | YES | NO | - | YES | NO | 100% SUTRA. Human approval boundary MUST NOT change. |
| 20 | Merge | pull_request_service.py, git_merge_service.py | YES | YES | YES | PARTIAL | YES | SUTRA: authorization + PR state update + audit. GitHub: actual ref update via API. CAS model changes. |
| 21 | Audit | audit.py, ChangeEvent, TaskEvent, GitPushEvent | YES | NO | - | YES | NO | SUTRA audit trail must not be replaced by GitHub history. May be correlated. |
| 22 | Agent revocation | agents.py, agent_dependencies.py | YES | NO | - | YES | NO | 100% SUTRA. Instantly revokes sessions via Redis. |
| 23 | Lifecycle state transitions | change_service.py, pull_request_service.py | YES | NO | - | YES | NO | SUTRA state machine is authoritative. |

---

## Detailed Analysis Per Operation Category

### A. Agent Identity

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Agent registration request | agent_registration.py | YES | NO | KEEP. Pure SUTRA. |
| Human approval of registration | agent_registration.py | YES | NO | KEEP. Pure SUTRA. |
| Agent creation (human-initiated) | agents.py | YES | NO | KEEP. Pure SUTRA. |
| Permanent token issuance | agents.py, security.py | YES | NO | KEEP. Never delegate token issuance. |
| Actor record creation | agents.py | YES | NO | KEEP. Actor is SUTRA identity spine. |

### B. Authentication

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Human JWT issuance | auth.py | YES | NO | KEEP. |
| Agent session creation | agent_dependencies.py | YES | NO | KEEP. SUTRA-issued, SUTRA-validated. |
| Agent session validation | agent_dependencies.py, Redis | YES | NO | KEEP. |
| Session heartbeat | agents.py | YES | NO | KEEP. |
| Session revocation | agent_dependencies.py, Redis | YES | NO | KEEP. Instant revocation is a SUTRA invariant. |

**Security invariant:** GitHub credentials (installation tokens, OAuth tokens) must NEVER replace the SUTRA session as the agent's primary identity token. They are downstream credentials scoped per-operation.

### C. Repository Discovery

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| List repositories for agent | repositories.py, Repository table | YES (authorization) | Partial (data) | KEEP authorization. Adapt to allow GitHub-backed repos. |
| Get repository metadata | repositories.py, Repository | YES (auth) | YES (data when GitHub) | Repository table stays; add `provider_type` and `provider_repo_id` fields. |
| Repository creation | repositories.py, RepositoryService | YES (record) | YES (actual repo) | RepositoryService becomes LocalRepositoryProvider. Add GitHubRepositoryProvider. |

### D. Repository Read (git clone / fetch)

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Auth gate for clone | git_http.py, agent_dependencies.py | YES | NO | KEEP auth gate. |
| repository.read capability check | authorization_service.py | YES | NO | KEEP. |
| Actual Git transport | git http-backend subprocess | NO | YES (GitHub) | Move behind RepositoryProvider interface. Local = current impl. GitHub = agent uses github.com URL with scoped token. |
| Credential delivery to agent | git_http.py (session token as password) | SUTRA issues | GitHub validates | NEW: SUTRA issues time-scoped GitHub token after capability check. Agent uses it to clone from github.com. |

**Key architectural decision for Step D:**
Currently: Agent -> SUTRA Git HTTP -> bare repo  
After migration: Agent -> SUTRA API (capability check) -> scoped GitHub token -> agent clones directly from github.com

SUTRA no longer proxies Git bytes. SUTRA issues credentials. This is a fundamental transport change.

### E. Repository Write (git push)

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Auth gate for push | git_http.py | YES | NO | KEEP auth gate (moved to token issuance). |
| repository.write capability check | authorization_service.py | YES | NO | KEEP. |
| Force-push/delete-branch guard | git_receive_policy_service.py, git_pre_receive.py | YES | NO | KEEP logic; GitHub push rules enforce at GitHub side. |
| Pre-receive hook | git_pre_receive.py | YES | NO | **NO GITHUB EQUIVALENT.** Replace with GitHub App required status check (check run) that SUTRA reports. |
| Actual Git transport | git http-backend subprocess | NO | YES (GitHub) | Agent pushes to github.com using SUTRA-issued scoped token. |
| Push event recording | git_push_event_service.py, GitPushEvent | YES (record) | NO | Replace local hook detection with GitHub push webhook processing. |

### F. Branch Operations

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Branch creation (agent) | Implicit in git push | NO | YES | With GitHub: branch API or implicit via push. |
| Branch deletion guard | git_receive_policy_service.py | YES | NO | Policy stays SUTRA. Enforcement: SUTRA check run blocks merge if violated. |
| Default branch | Repository.default_branch | YES (metadata) | YES (actual) | Keep metadata in SUTRA; sync from GitHub on import. |
| Branch protection rules | branch_protection_service.py, BranchProtectionRule | YES | NO (for SUTRA) | Keep SUTRA model. Add GitHub branch protection as optional surface. |

### G. Commit Operations

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Commit validation (SHA exists) | change_service.py (subprocess git cat-file) | NO (uses local repo) | YES (uses GitHub) | Replace local validation with GitHub commits API. |
| Commit SHA recording on Change | change_service.py, Change.resulting_commit | YES | NO | KEEP. resulting_commit is a SUTRA field. |
| Diff stats (files/additions/deletions) | change_service.py, ChangeFile | YES (record) | YES (data) | Replace local git diff with GitHub comparison API. |

### H. Change Model

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Change creation (intent + repo) | change_service.py, Change | YES | NO | KEEP ENTIRELY. Core SUTRA record. |
| operation_key idempotency | Change.operation_key, change_service.py | YES | NO | KEEP. SHA-256 fingerprint is SUTRA-owned. Adapt input fields if needed. |
| Status state machine (proposed/recorded/blocked/rejected) | change_service.py | YES | NO | KEEP ENTIRELY. |
| Evidence collection | change_service.py, ChangeFile | YES | NO | KEEP model. Data source adapts to GitHub API. |
| Policy evaluation on Change | change_policy_service.py | YES | NO | KEEP ENTIRELY. |
| ChangeEvent audit | change_event.py | YES | NO | KEEP ENTIRELY. |

### I. Evidence Collection

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Commit SHA as evidence | change_service.py | YES | NO | KEEP. |
| File diff stats | change_service.py (git show subprocess) | YES (record) | YES (data) | Adapt data source to GitHub comparison API. |
| CI result | ci_service.py, CIJob | YES (orchestration) | YES (execution) | SUTRA records; GitHub Actions may execute. |
| Push event as evidence | git_push_event_service.py | YES | NO | Adapt: local push hook -> GitHub push webhook. |

### J. Policy Evaluation

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Authorization policy | authorization_service.py | YES | NO | KEEP. Central invariant. |
| Conflict policy | change_policy_service.py, conflict_service.py | YES | NO | KEEP logic. Adapt conflict data source. |
| Risk policy | change_policy_service.py | YES | NO | KEEP ENTIRELY. |
| Dependency policy | change_policy_service.py, ChangeDependency | YES | NO | KEEP ENTIRELY. |
| Branch protection gate | branch_protection_service.py | YES | NO | KEEP ENTIRELY. |
| Pre-push policy | git_receive_policy_service.py | YES | NO | KEEP logic; adapt enforcement to GitHub check runs. |

### K. PR Creation

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| SUTRA PR record | pull_request_service.py, PullRequest | YES | NO | KEEP. SUTRA PullRequest is the authoritative record. |
| GitHub PR creation | (does not exist yet) | - | YES | NEW: GitHubRepositoryProvider.createPullRequest(). SUTRA PR becomes mirrored in GitHub. |
| PR uniqueness (per Change) | UNIQUE(source_change_id) | YES | NO | KEEP. SUTRA enforces uniqueness. |
| Authorization check | pull_request_service.py -> authorization_service.py | YES | NO | KEEP. |

### L. PR Review

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| SUTRA ChangeReview record | change_reviews.py, ChangeReview | YES | NO | KEEP ENTIRELY. This is the authoritative approval. |
| GitHub PR review | (does not exist yet) | - | YES | NEW: can surface SUTRA policy as a GitHub Check Run on the PR. |
| Requester != reviewer enforcement | pull_request_service.py | YES | NO | KEEP. Enforced in SUTRA. |
| Human-only approval | change_reviews.py (requires Human JWT) | YES | NO | KEEP. NEVER weaken. |
| Agent review (code comments) | agent_review_service.py, InlineReviewComment | YES | NO | KEEP. Agent comments are SUTRA-owned. |

### M. Human Approval Boundary

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Approve own review -> DENIED | change_reviews.py | YES | NO | KEEP. Hard rule. |
| Agent approves review -> DENIED | change_reviews.py (requires Human JWT) | YES | NO | KEEP. |
| Merge without review -> DENIED (if branch protection) | branch_protection_service.py | YES | NO | KEEP. |
| Agent self-merge -> DENIED | pull_requests.py (requires Human JWT) | YES | NO | KEEP. |

**This entire section is non-negotiable.** The GitHub migration must not weaken any of these checks.

### N. Merge

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| Merge authorization (Human JWT only) | pull_requests.py | YES | NO | KEEP. |
| Branch protection gate | branch_protection_service.py | YES | NO | KEEP. |
| Policy gate | pull_request_service.py -> change_policy_service.py | YES | NO | KEEP. |
| Actual ref update | git_merge_service.py (git update-ref CAS) | NO | YES (GitHub) | Replace GitMergeService local CAS with GitHub merge API. Add idempotency via PR state check. |
| Merge result recording | pull_request_service.py, PullRequest.merged_at | YES | NO | KEEP. SUTRA records the merge fact independently. |
| Audit event for merge | change_event.py | YES | NO | KEEP ENTIRELY. |

### O. Audit Trail

| Operation | Current File | SUTRA-owned? | GitHub-owned? | Decision |
|-----------|-------------|:---:|:---:|---------|
| ChangeEvent records | change_event.py | YES | NO | KEEP. SUTRA audit is non-negotiable. |
| TaskEvent records | task_event.py | YES | NO | KEEP. |
| GitPushEvent records | git_push_event.py | YES | NO | KEEP model; adapt source (webhook instead of hook). |
| PR state history | PullRequest.updated_at etc. | YES | NO | KEEP. |
| GitHub commit history | (does not exist yet) | NO | YES | Add optional correlation: SUTRA audit record includes pr_number, check_run_id, sha for cross-referencing. |
| GitHub PR comment timeline | (does not exist yet) | NO | YES | Not required in SUTRA audit; informational only. |

---

## Security-Critical Ownership Summary

The following **must remain SUTRA-owned and must not be delegated to GitHub**:

| Invariant | Enforced By | Risk if Delegated |
|-----------|-------------|------------------|
| Agent registration requires human approval | agent_registration.py (approve endpoint requires Human JWT) | Agents could self-register without human oversight |
| Registration does NOT grant repository access | agent_registration.py (no auto-grant) | Agent bypasses authorization model |
| Repository access requires explicit grant | agent_repository_access.py, AuthorizationService | Agent accesses any repo via GitHub credentials |
| Public repo does NOT bypass auth | authorization_service.py (explicit check) | Agents clone any public repo without SUTRA permission |
| Same-owner does NOT bypass auth | authorization_service.py (explicit check) | Agent accesses owner's other repos without grant |
| Session is SUTRA-issued | agent_dependencies.py | Rogue sessions bypass SUTRA revocation |
| Merge requires Human JWT | pull_requests.py | Agents self-merge |
| Approval requires different human | change_reviews.py | Requester self-approves |
| Agent revocation is instant | Redis revocation marker | Revoked agent continues operating |

---

## What GitHub Would Provide After Migration

| GitHub Capability | SUTRA's Role |
|------------------|-------------|
| Repository hosting | SUTRA authorizes access; GitHub stores objects |
| Git transport (clone/push/fetch) | SUTRA issues scoped credential; GitHub serves Git |
| Branches | SUTRA tracks default_branch; GitHub stores refs |
| Pull requests (UI + API) | SUTRA mirrors PR as GitHub PR; SUTRA PR record is authoritative |
| Pull request reviews (GitHub reviews) | SUTRA Check Run surfaces policy result; GitHub displays it |
| Merge execution | SUTRA authorizes + records; GitHub API executes ref update |
| Webhook events | SUTRA processes: push, pull_request, check_run, installation |
| Check runs | SUTRA creates check runs to surface policy decisions |
| Commit objects | GitHub stores; SUTRA records SHA as evidence |
| CI (GitHub Actions) | Optional: SUTRA records CI result; Actions executes |

---

## Provider Abstraction Interface (Required for Phase 3)

Based on this analysis, the RepositoryProvider interface must expose at minimum:

```python
class RepositoryProvider:
    # Repository management
    def create_repository(owner_id, name, visibility) -> ProviderRepository
    def get_repository(owner, name) -> ProviderRepository
    def delete_repository(repo_id) -> None

    # File content
    def read_file(repo, path, ref) -> bytes
    def list_files(repo, path, ref) -> list[FileEntry]

    # Branches
    def list_branches(repo) -> list[Branch]
    def create_branch(repo, branch_name, from_ref) -> Branch
    def get_branch(repo, branch_name) -> Branch

    # Commits
    def get_commit(repo, sha) -> Commit
    def commit_exists(repo, sha) -> bool
    def compare(repo, base, head) -> CompareResult  # diff stats, files changed

    # Pull requests
    def create_pull_request(repo, title, body, head, base) -> ProviderPR
    def get_pull_request(repo, pr_id) -> ProviderPR
    def list_pull_request_files(repo, pr_id) -> list[FileEntry]

    # Merge
    def merge_pull_request(repo, pr_id, merge_method, commit_message) -> MergeResult

    # Checks
    def create_check_run(repo, name, head_sha, status, conclusion, output) -> CheckRun
    def update_check_run(repo, check_run_id, status, conclusion, output) -> CheckRun

    # Webhooks / Events
    def verify_webhook_signature(payload, signature, secret) -> bool
    def parse_webhook_event(event_type, payload) -> ProviderEvent

    # Credentials (for agent use)
    def issue_scoped_credential(repo, permissions, ttl_seconds) -> ScopedCredential
```

Current SUTRA local implementation becomes: `LocalRepositoryProvider`
GitHub implementation becomes: `GitHubRepositoryProvider`

---

## Files That Will Change vs. Files That Will Not Change

### Will NOT change (SUTRA core — preserve as-is)

- `backend/app/services/authorization_service.py`
- `backend/app/api/agent_dependencies.py`
- `backend/app/api/agent_registration.py`
- `backend/app/api/agent_repository_access.py`
- `backend/app/api/agent_protocol.py`
- `backend/app/services/change_service.py`
- `backend/app/services/change_policy_service.py`
- `backend/app/services/branch_protection_service.py`
- `backend/app/services/session_reaper_worker.py`
- `backend/app/api/audit.py`
- `backend/app/models/` (all ORM models — may ADD fields, never delete during migration)

### Will change (adapt to provider abstraction)

- `backend/app/api/git_http.py` — auth gate preserved; transport moves behind provider
- `backend/app/api/pull_requests.py` — add GitHub PR mirroring call
- `backend/app/services/pull_request_service.py` — call provider.merge_pull_request() instead of GitMergeService
- `backend/app/services/conflict_service.py` — add GitHub-backed conflict check
- `backend/app/services/change_service.py` — adapt commit validation to use provider

### New files (Phase 3+)

- `backend/app/providers/base.py` — RepositoryProvider abstract interface
- `backend/app/providers/local_provider.py` — LocalRepositoryProvider (current git subprocess impl)
- `backend/app/providers/github_provider.py` — GitHubRepositoryProvider (GitHub API impl)
- `backend/app/providers/github_app.py` — GitHub App auth + installation token management
- `backend/app/api/webhooks/github.py` — GitHub webhook processing
- `backend/app/services/github_check_service.py` — Surfacing SUTRA policy as GitHub Check Runs

### Will become local provider (not deleted)

- `backend/app/services/repository_service.py` -> LocalRepositoryProvider.create_repository()
- `backend/app/services/git_merge_service.py` -> LocalRepositoryProvider.merge()
- `backend/app/services/repository_browser_service.py` -> LocalRepositoryProvider.read_file()
- `backend/app/git_pre_receive.py` -> Used only by LocalRepositoryProvider

---

*This document was produced by Phase 1 mapping. No code was modified.*
