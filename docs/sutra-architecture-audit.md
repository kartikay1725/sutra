# SUTRA Architecture Audit

**Phase:** 0 — Inventory Only (no code modifications)
**Date:** 2026-08-31
**Status:** Complete. No code was changed.

---

## 1. Current Architecture Overview

SUTRA is a self-hosted AI-native engineering control plane. It functions as a **full Git platform** — it hosts bare Git repositories on disk and implements its own Git Smart HTTP transport, pre-receive policy gates, pull request system, merge engine, CI runner, branch protection, change lifecycle, review workflow, and audit trail.

**Technology Stack:**
- **Backend:** Python, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2
- **Database:** SQLite (development) / PostgreSQL (production via psycopg3)
- **Cache / Ephemeral state:** Redis
- **Authentication:** Argon2 password hashing (pwdlib), PyJWT for human sessions
- **Git transport:** System `git http-backend` subprocess
- **AI integration:** Groq API
- **Frontend:** Next.js (TypeScript)
- **Rate limiting:** SlowAPI

**Conceptual architecture:**

```
AI Agents (Codex / Claude / Cursor)
        |
SUTRA HTTP API  (FastAPI / Uvicorn — /v1/* /git/*)
        |
+-------+----------------------------------+
| SUTRA CONTROL PLANE                      |
|                                          |
|  Agent Identity  (Actor / Agent)         |
|  Sessions        (AgentSession)          |
|  Capabilities    (AgentRepositoryAccess) |
|  Authorization   (AuthorizationService)  |
|  Policy          (ChangePolicyService)   |
|  Changes         (Change, ChangeFile)    |
|  Review/Approval (ChangeReview)          |
|  Audit           (ChangeEvent, etc.)     |
|  Task lifecycle  (Task, TaskEvent)       |
|  PR lifecycle    (PullRequest)           |
|  Branch protect  (BranchProtectionRule)  |
|  CI              (CIJob)                 |
|  Knowledge Graph (KnowledgeNode/Edge)    |
+------------------------------------------+
        |
LOCAL GIT STORAGE (bare repos on disk)
  ./data/repositories/<uuid>/
  git http-backend (subprocess)
  pre-receive hook -> git_pre_receive.py
  GitMergeService (subprocess git)
  RepositoryService (git init / push)
```

---

## 2. Current 15-Step Agent Lifecycle

As implemented in `GET /v1/agent-info` and `POST /v1/agent-protocol/handshake`:

| Step | Actor | Action | Endpoint |
|------|-------|--------|----------|
| 1 | Human | Login -> Human JWT | POST /v1/auth/login |
| 2 | Human | Create Agent -> permanent token (returned once) | POST /v1/agents |
| 3 | Human | Grant repo access | POST /v1/repositories/{owner}/{repo}/agents |
| 4 | Agent | Create AgentSession (15 min TTL) | POST /v1/agents/session |
| 5 | Agent | Heartbeat every 30-60 s | POST /v1/agents/heartbeat |
| 6 | Agent | git clone via Smart HTTP | GET /git/{owner}/{repo}.git/info/refs |
| 7 | Agent | Code changes + git push | POST /git/{owner}/{repo}.git/git-receive-pack |
| 8 | Agent | Create Change record | POST /v1/changes/agent (change.create required) |
| 9 | Agent | Record commit evidence | POST /v1/changes/{id}/agent-commit (change.commit required) |
| 10 | Agent | Finalize Change | POST /v1/changes/{id}/agent-finalize |
| 11 | Agent | Create Pull Request | POST /v1/pull-requests/agent |
| 12 | Agent | Notify human | (notification / message) |
| 13 | Human | Request review | POST /v1/changes/{id}/reviews |
| 14 | Different Human | Approve review (requester != reviewer enforced) | POST /v1/changes/{id}/reviews/{rid}/approve |
| 15 | Human | Merge PR (human-only) | POST /v1/pull-requests/{id}/merge |

**Alternative fresh-agent registration flow:**

1. Agent calls `POST /v1/agents/register` (public, no auth)
2. SUTRA returns: `registration_id`, `polling_token`, `temporary_push_token`
3. Agent polls `GET /v1/agents/register/{id}/status`
4. Human approves via `POST /v1/agents/registrations/{id}/approve`
5. Agent retrieves permanent token; then follows Step 4 above

---

## 3. Exact Files Implementing Every Lifecycle Step

### Step 1 — Human Authentication

| File | Role |
|------|------|
| `backend/app/api/auth.py` | POST /v1/auth/login, JWT issuance, registration, OTP, WebAuthn |
| `backend/app/api/dependencies.py` | get_current_user — JWT validation dependency |
| `backend/app/models/user.py` | User ORM model |
| `backend/app/models/user_session.py` | UserSession model |
| `backend/app/core/security.py` | hash_password, verify_password |

### Step 2 — Agent Creation (Human-initiated)

| File | Role |
|------|------|
| `backend/app/api/agents.py` | POST /v1/agents — creates Agent + Actor records, returns one-time token |
| `backend/app/models/agent.py` | Agent ORM model |
| `backend/app/models/actor.py` | Actor ORM model (shared identity for humans and agents) |
| `backend/app/core/security.py` | Token hashing |

### Step 2 (alt) — Agent Self-Registration

| File | Role |
|------|------|
| `backend/app/api/agent_registration.py` | POST /v1/agents/register, GET status, approve/reject |
| `backend/app/models/agent_registration.py` | AgentRegistrationRequest model |
| `backend/app/core/redis_service.py` | Temporary push token atomic consumption |

### Step 3 — Repository Access Grant

| File | Role |
|------|------|
| `backend/app/api/agent_repository_access.py` | POST /v1/repositories/{owner}/{repo}/agents — grant/revoke/list |
| `backend/app/models/agent_repository_access.py` | AgentRepositoryAccess model (agent x repository x permissions) |

### Step 4 — Agent Session Creation

| File | Role |
|------|------|
| `backend/app/api/agents.py` | POST /v1/agents/session endpoint |
| `backend/app/api/agent_dependencies.py` | authenticate_agent_token, create_agent_session |
| `backend/app/models/agent_session.py` | AgentSession model |
| `backend/app/core/redis_service.py` | Session cache write |
| `backend/app/services/session_reaper_worker.py` | Background reaping of expired sessions |

### Step 5 — Heartbeat / Session Validation

| File | Role |
|------|------|
| `backend/app/api/agents.py` | POST /v1/agents/heartbeat |
| `backend/app/api/agent_dependencies.py` | validate_agent_session_token, get_current_agent_session |
| `backend/app/core/redis_service.py` | Fast revocation check |

### Step 6 — Git Clone / Fetch

| File | Role |
|------|------|
| `backend/app/api/git_http.py` | GET /git/{owner}/{repo}.git/info/refs |
| `backend/app/api/git_http.py` | authenticate_basic, authorize_repository_access, run_git_http_backend |
| `backend/app/services/authorization_service.py` | AuthorizationService.check(capability="repository.read") |
| System git http-backend | Actual Git pack protocol handling (subprocess) |

### Step 7 — Git Push

| File | Role |
|------|------|
| `backend/app/api/git_http.py` | POST /git/{owner}/{repo}.git/git-receive-pack |
| `backend/app/git_pre_receive.py` | Synchronous pre-receive Git hook (Python subprocess via Git) |
| `backend/app/services/git_receive_policy_service.py` | GitReceivePolicyService.evaluate — force-push guard, delete guard |
| `backend/app/services/authorization_service.py` | Authorization check inside hook |
| `backend/app/services/git_push_event_service.py` | GitPushEventService.create_event — persists transport fact |
| `backend/app/models/git_push_event.py` | GitPushEvent model with HMAC integrity |
| `backend/app/services/git_push_event_integrity.py` | HMAC-SHA256 integrity for push events |

### Step 8 — Change Creation

| File | Role |
|------|------|
| `backend/app/api/changes.py` | POST /v1/changes/agent |
| `backend/app/services/change_service.py` | ChangeService.create_agent_change — capability check, operation_key dedup |
| `backend/app/models/change.py` | Change model (proposed/recorded/blocked/rejected) |
| `backend/app/services/authorization_service.py` | change.create capability check |

### Step 9 — Commit Evidence Recording

| File | Role |
|------|------|
| `backend/app/api/changes.py` | POST /v1/changes/{id}/agent-commit |
| `backend/app/services/change_service.py` | Records resulting_commit, validates SHA exists in bare repo |
| `backend/app/models/change_file.py` | Diff stats (additions, deletions) |
| `backend/app/models/change_event.py` | Immutable audit event for commit recording |
| `backend/app/services/authorization_service.py` | change.commit capability check |

### Step 10 — Change Finalization

| File | Role |
|------|------|
| `backend/app/api/changes.py` | POST /v1/changes/{id}/agent-finalize |
| `backend/app/services/change_service.py` | Runs policy evaluation, updates status |
| `backend/app/services/change_policy_service.py` | ChangePolicyService.evaluate — conflict + dependency + risk |
| `backend/app/services/conflict_service.py` | Git merge-base conflict analysis |
| `backend/app/services/git_push_event_processor.py` | Async: correlates push events to Changes |

### Step 11 — Pull Request Creation

| File | Role |
|------|------|
| `backend/app/api/pull_requests.py` | POST /v1/pull-requests/agent |
| `backend/app/services/pull_request_service.py` | PullRequestService.create_from_agent — auth, change validation, uniqueness |
| `backend/app/models/pull_request.py` | PullRequest model |
| `backend/app/services/authorization_service.py` | Capability checks |

### Step 13 — Review Request (Human)

| File | Role |
|------|------|
| `backend/app/api/change_reviews.py` | POST /v1/changes/{id}/reviews |
| `backend/app/models/change_review.py` | ChangeReview model |

### Step 14 — Review Approval (Different Human)

| File | Role |
|------|------|
| `backend/app/api/change_reviews.py` | POST /v1/changes/{id}/reviews/{rid}/approve |
| `backend/app/services/pull_request_service.py` | Requester != reviewer enforcement |
| `backend/app/models/change_event.py` | Audit event for approval |

### Step 15 — Merge (Human-only)

| File | Role |
|------|------|
| `backend/app/api/pull_requests.py` | POST /v1/pull-requests/{id}/merge (Human JWT only) |
| `backend/app/services/pull_request_service.py` | PullRequestService.merge — full orchestration |
| `backend/app/services/git_merge_service.py` | GitMergeService.execute_server_side_merge — FF + 3-way merge, CAS ref update |
| `backend/app/services/branch_protection_service.py` | Gates merge against protection rules |
| `backend/app/models/change_event.py` | Audit event for merge |

---

## 4. Database Tables / Models

### Identity and Authentication

| Table | Model | Purpose |
|-------|-------|---------|
| actors | Actor | Polymorphic identity (type: human/agent) — shared authorization subject |
| users | User | Human accounts |
| user_sessions | UserSession | Human JWT sessions |
| webauthn_credentials | WebAuthnCredential | Passkey credentials |
| agents | Agent | Agent records (token_hash, token_prefix, owner_id, status) |
| agent_sessions | AgentSession | Short-lived agent sessions (15 min TTL, idle timeout 120 s) |
| agent_registration_requests | AgentRegistrationRequest | Registration flow records |

### Repository and Authorization

| Table | Model | Purpose |
|-------|-------|---------|
| repositories | Repository | Repo metadata (slug, storage_key, owner_id, visibility, default_branch) |
| agent_repository_access | AgentRepositoryAccess | Agent x repository x capability permissions (JSON list) |
| branch_protection_rules | BranchProtectionRule | Branch protection config per repository |

### Change Lifecycle

| Table | Model | Purpose |
|-------|-------|---------|
| changes | Change | Change record (intent, base_commit, resulting_commit, status, operation_key) |
| change_files | ChangeFile | Per-file diff stats |
| change_events | ChangeEvent | Immutable audit trail of status transitions |
| change_reviews | ChangeReview | Review requests/approvals (requested_by != reviewer_id) |
| change_dependencies | ChangeDependency | Dependency graph between Changes |

### Git Events

| Table | Model | Purpose |
|-------|-------|---------|
| git_push_events | GitPushEvent | Persisted push facts (HMAC-SHA256, worker lease, retry state) |

### Pull Requests and CI

| Table | Model | Purpose |
|-------|-------|---------|
| pull_requests | PullRequest | PR (title, target_branch, source_commit, status) |
| inline_review_comments | InlineReviewComment | Inline code comments |
| ci_jobs | CIJob | CI job records |

### Tasks and Knowledge

| Table | Model | Purpose |
|-------|-------|---------|
| tasks | Task | Engineering task (status, priority, assigned_agent_id, resulting_change_id) |
| task_events | TaskEvent | Task lifecycle audit events |
| knowledge_nodes | KnowledgeNode | Code entity nodes |
| knowledge_edges | KnowledgeEdge | Entity relationships |

---

## 5. APIs Involved

### Agent-Facing

| Path | Method | Auth |
|------|--------|------|
| /v1/agents/register | POST | None (public) |
| /v1/agents/register/{id}/status | GET | polling_token |
| /v1/agents/registrations/{id}/approve | POST | Human JWT |
| /v1/agents | POST | Human JWT |
| /v1/agents/session | POST | permanent agent token |
| /v1/agents/heartbeat | POST | AgentSession |
| /v1/agent-protocol/handshake | POST | AgentSession |
| /v1/agent-info | GET | None |
| /git/{owner}/{repo}.git/* | GET/POST | Basic Auth (agent session) |

### Repository Management

| Path | Method | Auth |
|------|--------|------|
| /v1/repositories | GET/POST | Human JWT or AgentSession |
| /v1/repositories/{owner}/{repo}/agents | GET/POST/DELETE | Human JWT only |
| /v1/repository-browser/{owner}/{repo}/tree | GET | Human JWT or AgentSession |

### Change and PR Lifecycle

| Path | Method | Auth |
|------|--------|------|
| /v1/changes/agent | POST | AgentSession (change.create) |
| /v1/changes/{id}/agent-commit | POST | AgentSession (change.commit) |
| /v1/changes/{id}/agent-finalize | POST | AgentSession |
| /v1/changes/{id}/reviews | POST | Human JWT |
| /v1/changes/{id}/reviews/{rid}/approve | POST | Human JWT (different user) |
| /v1/pull-requests/agent | POST | AgentSession |
| /v1/pull-requests/{id}/merge | POST | Human JWT only |

---

## 6. Current Repository Ownership Model

SUTRA currently **owns the entire repository infrastructure**:

1. **Physical storage:** Bare Git repos at `./data/repositories/<repository_uuid>/`
2. **Transport:** `git http-backend` subprocess inside the FastAPI process
3. **Pre-receive gate:** Python hook installed at `hooks/pre-receive` in every bare repo
4. **Merge engine:** `GitMergeService` — direct `git update-ref` with CAS on local filesystem
5. **Branch protection:** `BranchProtectionService` — SUTRA enforces its own rules
6. **Repository browser:** `RepositoryBrowserService` — reads files from bare repos via subprocess
7. **Repository record:** `Repository.storage_key` maps to `{storage_path}/{uuid}` on disk

**Key coupling:** `storage_key` = UUID = filesystem directory name. Every service that touches Git resolves through this key.

---

## 7. Dependencies Between Lifecycle Stages

```
Human Auth (JWT)
    |
Agent Creation (JWT required)   OR   Agent Self-Registration (public)
    |                                        | (human polls + approves)
    +<---------------------------------------+
Repository Creation (may auto-create on approval)
    |
Repository Access Grant (JWT + repo ownership)
    |
AgentSession Creation (permanent token)
    |  [session must stay active for all operations below]
    |
Git Clone (repository.read grant required)
    |
Code Modification + Git Push
    | [pre-receive hook: active agent + repository.write grant checked synchronously]
    |
GitPushEvent persisted (HMAC integrity)
    | [async worker: GitPushEventProcessor correlates push to Change]
    |
Change proposed (operation_key idempotency prevents duplicates)
    |
Agent records resulting_commit (change.commit capability required)
    |
Change finalization -> Policy evaluation (conflict + dependency + risk + capability)
    |
PR created (linked to Change + commit)
    |
Human requests review (ChangeReview record)
    |
DIFFERENT human approves (requester != reviewer — database-enforced)
    |
Branch protection gates evaluated
    |
GitMergeService executes merge (CAS atomic ref update)
    |
PR -> merged, ChangeEvent audit record written
```

**Hard dependencies:**
- Session must remain active throughout Steps 4-11
- `resulting_commit` must exist in the bare repo before it can be recorded on Change
- Review must be approved before merge (if branch protection requires it)
- Agent cannot approve its own review request — enforced by checking reviewer_id != requested_by

---

## 8. Provider-Specific vs. SUTRA-Core Code

### Provider-Specific (Local Git — would move behind GitHub adapter)

| File | Nature |
|------|--------|
| `backend/app/services/repository_service.py` | Bare repo creation, git init, initial commit bootstrap, ensure_receive_hook |
| `backend/app/api/git_http.py` | Git Smart HTTP proxy via git http-backend subprocess |
| `backend/app/git_pre_receive.py` | Pre-receive hook implementation |
| `backend/app/services/git_merge_service.py` | Server-side Git merge via subprocess git |
| `backend/app/services/repository_browser_service.py` | Reads files from bare repo filesystem |
| `backend/app/api/repository_browser.py` | Repository browser API (backed by local bare repo) |
| `backend/app/services/conflict_service.py` | Git merge-base analysis via subprocess |

### SUTRA Control-Plane Core (Must NOT be touched by provider migration)

| File | Nature |
|------|--------|
| `backend/app/services/authorization_service.py` | SUTRA's central security decision point |
| `backend/app/api/agent_dependencies.py` | Session lifecycle, validation, revocation |
| `backend/app/api/agent_registration.py` | Agent registration flow (device-code-like) |
| `backend/app/api/agent_repository_access.py` | Repository access grants (human-only) |
| `backend/app/api/agent_protocol.py` | Protocol handshake + discovery |
| `backend/app/services/change_service.py` | Change lifecycle state machine |
| `backend/app/services/change_policy_service.py` | Policy evaluation engine |
| `backend/app/services/pull_request_service.py` | PR orchestration |
| `backend/app/services/branch_protection_service.py` | Branch protection rule enforcement |
| `backend/app/services/git_receive_policy_service.py` | Pre-receive authorization (delegates to AuthorizationService) |
| `backend/app/services/session_reaper_worker.py` | Session expiry reaping |
| `backend/app/api/audit.py` | Org-scoped audit trail |
| `backend/app/models/` (all) | All ORM models are SUTRA-owned |

### Partially Provider-Specific (logic is SUTRA, data source depends on provider)

| File | Nature |
|------|--------|
| `backend/app/services/git_push_event_service.py` | Event model is SUTRA-owned; data comes from local Git push |
| `backend/app/services/git_push_event_processor.py` | Correlation logic is SUTRA-owned; will need adaptation for GitHub webhooks |

---

## 9. Which Parts Are True SUTRA Functionality

The following are **SUTRA control-plane responsibilities** that must remain SUTRA-owned regardless of Git provider:

1. **Agent identity** — Agent, Actor tables; POST /v1/agents
2. **Agent registration** — AgentRegistrationRequest; polling token flow; human approval gate
3. **Session management** — AgentSession; 15-min TTL + idle timeout; Redis revocation
4. **Repository access authorization** — AgentRepositoryAccess; AuthorizationService.check()
5. **Capability model** — repository.read/write, change.create/commit, knowledge_graph.*
6. **Change state machine** — Change model (proposed -> recorded -> blocked/rejected)
7. **Policy evaluation** — ChangePolicyService — conflict + dependency + risk + capability
8. **Review lifecycle** — ChangeReview; requester != reviewer invariant; human-only approval
9. **Pull request orchestration** — PullRequest state machine; merge authorization (human-only)
10. **Branch protection rules** — BranchProtectionRule; gate evaluation before merge
11. **Audit trail** — ChangeEvent, TaskEvent, GitPushEvent — SUTRA audit records
12. **Agent revocation** — Agent.is_active = False; AgentSession.status = revoked; Redis marker
13. **Task lifecycle** — Task, TaskEvent — agent task assignment and tracking
14. **Knowledge graph** — KnowledgeNode, KnowledgeEdge — scoped to repository authorization
15. **CI orchestration** — CIJob, CIRunner, CISandbox

---

## 10. Migration Risks

### High Risk

| Risk | Description |
|------|-------------|
| Pre-receive hook | Installed as shell script in bare repo. GitHub does NOT support custom server-side pre-receive hooks. SUTRA policy gate must be reimplemented as GitHub App check run/status. This is the most critical architectural difference. |
| Merge CAS | GitMergeService does direct git update-ref CAS on local filesystem. With GitHub, merge must go through GitHub API. Entire idempotency strategy changes. |
| operation_key idempotency | Currently: repository + actor + ref + before_sha + after_sha. With GitHub, facts come from webhook events. Dedup strategy must be redesigned. |
| Session + Git HTTP coupling | AgentSession token is the Git HTTP password. With GitHub, Git operations go directly to github.com. The unified session-to-Git model breaks. New credential delegation model required. |
| storage_key coupling | Every service resolves repositories via storage_key -> filesystem path. GitHub repos use owner/repo slug, not a local UUID. Must introduce abstraction. |
| Repository browser | RepositoryBrowserService reads from bare repo filesystem. GitHub equivalent is the Contents API (requires network call). |

### Medium Risk

| Risk | Description |
|------|-------------|
| Conflict detection | ConflictService runs git merge-base locally. GitHub exposes mergeable + merge_commit_sha in PR. Different data model. |
| Push event integrity | GitPushEvent uses HMAC-SHA256 with EVENT_INTEGRITY_KEY. GitHub webhooks use HMAC-SHA256 with webhook secret. Compatible model; new verification code needed. |
| Agent credential delegation | Agents currently auth directly to SUTRA Git. With GitHub: agent -> SUTRA policy -> time-limited GitHub token. Design required. |
| CI sandbox | CISandbox and CIRunner are custom. GitHub CI = GitHub Actions. Integration model TBD. |

### Low Risk (Provider-independent, minimal change needed)

| Risk | Description |
|------|-------------|
| AuthorizationService | Pure SUTRA logic. No provider dependency. Unchanged. |
| Session management | Pure SUTRA. Evolves independently. |
| Change model | No provider dependency beyond resulting_commit being a real SHA. |
| Review model | Human approval boundary is independent of Git provider. |
| Audit model | Can be augmented with GitHub event correlation fields (pr_number, check_run_id). |
| Task model | Fully independent of Git provider. |
| Knowledge Graph | Fully independent of Git provider. |

---

## Appendix: Key Configuration

| Variable | Purpose |
|----------|---------|
| DATABASE_URL | SQLite (dev) / PostgreSQL (prod) |
| REDIS_URL | Redis for session cache + rate limits |
| JWT_SECRET | Human JWT signing |
| EVENT_INTEGRITY_KEY | HMAC-SHA256 key for GitPushEvent integrity |
| REPOSITORY_STORAGE_PATH | Root path for bare Git repository storage |
| SUTRA_BASE_URL | Base URL for absolute links |
| GROQ_API_KEY | Groq AI integration |

> **IMPORTANT:** No GitHub credentials of any kind exist in the current environment. GitHub integration does not exist yet.

---

*This document was produced by Phase 0 audit. No code was modified.*
