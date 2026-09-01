# SUTRA Target Control-Plane Architecture

**Phase:** 2 — Target Architecture Specification  
**Date:** 2026-08-31  
**Status:** Design Document (No code modifications)

---

## 1. Executive Summary & Control-Plane Mission

SUTRA is evolving from a self-hosted Git platform into an **AI-Native Engineering Control Plane**.

In this target architecture:
- **SUTRA remains the sovereign governance, identity, policy, review, and audit authority.**
- **GitHub serves as the first external repository and engineering substrate.**
- **Local Git remains supported as the built-in default provider.**
- **AI Agents interface directly with SUTRA for identity, capability negotiation, evidence, and PR management.**

```
                           AI AGENTS
                  (Codex, Claude, Cursor, Custom)
                                │
               ┌────────────────┴────────────────┐
               │    SUTRA CONTROL PLANE (REST)   │
               │                                 │
               │  • Identity & Sessions          │
               │  • Capabilities & Authorization │
               │  • Change Ledger & Evidence     │
               │  • Deterministic Policy Engine  │
               │  • Human Review & Approval Gate │
               │  • Immutable Audit Trail        │
               └────────────────┬────────────────┘
                                │
                  [RepositoryProvider Interface]
                                │
               ┌────────────────┴────────────────┐
               │                                 │
               ▼                                 ▼
      [GitHub App Provider]            [Local Git Provider]
               │                                 │
               ▼                                 ▼
    GitHub (API, PR, Checks,         Local Bare Git Host
     Actions, Branch Rulesets)       (git http-backend, Hooks)
```

---

## 2. Authoritative Control-Plane APIs vs. Provider Adapters

### A. Authoritative SUTRA Control-Plane APIs (Unchanged Core)
These APIs define the SUTRA operating model. They are **provider-agnostic** and strictly SUTRA-owned:

| API Endpoint | Authority & Responsibility |
|--------------|----------------------------|
| `POST /v1/auth/login`, `/v1/auth/*` | Human user authentication, JWT session lifecycle, passkeys. |
| `POST /v1/agents/register`, `GET /status` | Device-flow agent self-registration and human approval. |
| `POST /v1/agents`, `GET /v1/agents/*` | Agent identity creation, token issuance, active state control. |
| `POST /v1/agents/session`, `/heartbeat` | Short-lived AgentSession issuance (15 min TTL), Redis-backed validation. |
| `POST /v1/repositories/{owner}/{repo}/agents` | Human-only capability grants (`AgentRepositoryAccess`). |
| `POST /v1/changes/agent` | Agent Change proposition, `operation_key` idempotency. |
| `POST /v1/changes/{id}/agent-commit` | Commit evidence attachment, diff statistics recording. |
| `POST /v1/changes/{id}/agent-finalize` | Trigger deterministic policy evaluation (`ChangePolicyService`). |
| `POST /v1/changes/{id}/reviews` | Human review request creation. |
| `POST /v1/changes/{id}/reviews/{rid}/approve` | Human review approval (Requester ≠ Reviewer invariant enforced). |
| `POST /v1/pull-requests/agent` | PR orchestration record creation. |
| `POST /v1/pull-requests/{id}/merge` | Human-only PR merge authorization and audit recording. |
| `GET /v1/organizations/{id}/audit-logs` | Immutable org-scoped audit log generation. |
| `GET /v1/knowledge-graph/*` | Semantic code graph traversal scoped to authorized repositories. |
| `POST /v1/agent-protocol/*` | Machine protocol discovery, capabilities polling, task assignment. |

---

### B. Provider Adapter Layer (New & Adapted Components)
These components translate SUTRA control-plane operations into substrate-specific actions:

| Component / Endpoint | Provider Role (GitHub / Local) |
|----------------------|--------------------------------|
| `POST /v1/repositories/{owner}/{repo}/token` *(New)* | Token Broker: Exchanges valid SUTRA AgentSession for short-lived, repo-scoped GitHub Installation Token. |
| `POST /v1/webhooks/github` *(New)* | Ingests GitHub webhooks (`push`, `pull_request`, `check_run`), verifies HMAC signature, and feeds SUTRA event workers. |
| `GitHubCheckService` *(New)* | Synchronizes SUTRA `ChangePolicy` decisions to GitHub PRs as GitHub Check Runs. |
| `GitHubRepositoryProvider` *(New)* | Implements `RepositoryProvider` for GitHub (PR creation, merge API, branch queries, file reads). |
| `LocalRepositoryProvider` *(Adapted)* | Wraps existing `git http-backend`, `RepositoryService`, and `GitMergeService` under `RepositoryProvider`. |
| `/git/{owner}/{repo}.git/*` *(Local Only)* | Continues serving local Git repositories when local provider is active. |

---

## 3. End-to-End Target Lifecycle Sequence

```
1. Agent Registration & Identity:
   Agent ──(POST /v1/agents/register)──► SUTRA ──(Wait for Human)──► Human Approves ──► Permanent Token

2. Session Establishment:
   Agent ──(POST /v1/agents/session)──► SUTRA ──► Validates Token ──► Issues SUTRA AgentSession (15-min TTL)

3. Repository & Capability Discovery:
   Agent ──(POST /v1/agent-protocol/poll)──► SUTRA ──► Returns authorized repositories and granted capabilities

4. Provider Credential Delegation:
   Agent ──(POST /v1/repositories/{o}/{r}/token)──► SUTRA
   SUTRA AuthorizationService verifies: Active Session + repository.write
   SUTRA ──(GitHub App API)──► Requests 10-min GitHub Installation Token
   SUTRA ──► Returns scoped `ghs_...` token & GitHub clone URL to Agent

5. Engineering Work & Git Push:
   Agent clones from `github.com` using `ghs_...`
   Agent creates local branch `agent/feature-x`, commits changes
   Agent pushes branch to `github.com`

6. Webhook Observation & Evidence Ingestion:
   GitHub ──(push webhook + HMAC)──► SUTRA `/v1/webhooks/github`
   SUTRA records `GitPushEvent`, verifies commit SHAs, extracts file diff statistics

7. Change & PR Creation in SUTRA:
   Agent ──(POST /v1/changes/agent)──► SUTRA (Records Change)
   Agent ──(POST /v1/changes/{id}/agent-commit)──► SUTRA (Attaches SHA)
   Agent ──(POST /v1/pull-requests/agent)──► SUTRA
   SUTRA `GitHubRepositoryProvider` creates corresponding Pull Request on GitHub

8. Policy Evaluation & Check Run Reporting:
   SUTRA `ChangePolicyService` evaluates: Capabilities + Conflicts + Dependencies + Risk
   SUTRA `GitHubCheckService` ──► Creates Check Run on GitHub PR:
      ├─ Policy Passed: Check Run = `SUCCESS`
      └─ Policy Blocked: Check Run = `FAILURE` (Details link to SUTRA)

9. Human Review & Approval:
   Human Reviewer logs into SUTRA UI ──(POST /v1/changes/{id}/reviews/{rid}/approve)
   SUTRA enforces: `reviewer_id != requester_id` and Human JWT required
   SUTRA marks ChangeReview and PullRequest as `APPROVED`
   SUTRA updates GitHub Check Run to `SUCCESS`

10. Authorized Merge & Final Audit:
    Human ──(POST /v1/pull-requests/{id}/merge)──► SUTRA
    SUTRA verifies branch protection rules & all approval conditions
    SUTRA `GitHubRepositoryProvider` calls GitHub Merge API (`MERGE` / `SQUASH`)
    GitHub merges PR ref
    SUTRA records immutable `ChangeEvent(merged)` and `AuditLogEntry`
```

---

## 4. Provider Abstraction Architecture (`RepositoryProvider`)

```python
class RepositoryProvider(ABC):
    """Abstract interface governing all repository substrates."""

    @abstractmethod
    async def create_repository(self, owner: str, name: str, visibility: str) -> ProviderRepoMetadata: ...

    @abstractmethod
    async def get_repository(self, owner: str, name: str) -> ProviderRepoMetadata: ...

    @abstractmethod
    async def read_file(self, owner: str, name: str, path: str, ref: str) -> bytes: ...

    @abstractmethod
    async def list_files(self, owner: str, name: str, path: str, ref: str) -> list[FileEntry]: ...

    @abstractmethod
    async def create_pull_request(self, owner: str, name: str, title: str, body: str, head: str, base: str) -> ProviderPR: ...

    @abstractmethod
    async def merge_pull_request(self, owner: str, name: str, pr_number: int, commit_title: str, method: str) -> ProviderMergeResult: ...

    @abstractmethod
    async def create_or_update_check_run(self, owner: str, name: str, head_sha: str, name_key: str, status: str, conclusion: str, summary: str) -> CheckRunResult: ...

    @abstractmethod
    async def issue_scoped_transport_token(self, owner: str, name: str, permissions: dict[str, str], ttl_seconds: int) -> ScopedTokenResult: ...

    @abstractmethod
    async def revoke_transport_token(self, token: str) -> bool: ...
```

---

## 5. Unresolved Architecture Decisions Requiring Human Approval

Before proceeding to Phase 3 (Interface Specification & Provider Core), human approval is requested on the following architectural decisions:

| # | Architecture Decision | Recommended Option | Alternatives |
|---|----------------------|--------------------|--------------|
| **D1** | **Repository Storage Model** | **Hybrid / Dual-Provider:** Existing local repositories continue using `LocalRepositoryProvider`; newly imported/linked repositories specify `provider_type="github"`. | GitHub-Only (Discontinue local Git entirely). |
| **D2** | **GitHub App Installation Scope** | **Organization-level Installation:** GitHub App installed on the user's/org's GitHub account with access to selected repositories. | User-level Personal Access Tokens (PATs) (Not recommended: lacks fine-grained check runs and App identity). |
| **D3** | **Check Run Enforcement Policy** | **Strict Required Status Check:** GitHub repository rulesets require the SUTRA Policy Check Run to pass before merge is enabled on GitHub. | Informational-only Check Run (Relies solely on SUTRA API for merge). |
| **D4** | **Agent Git Transport Mode** | **Direct GitHub Transport:** SUTRA issues short-lived GitHub App tokens; agents clone/push directly to `github.com`. | SUTRA Smart HTTP Reverse Proxy (SUTRA proxies all Git packfiles; higher network overhead on SUTRA). |
| **D5** | **Merge Execution Authority** | **SUTRA API Initiated Merge:** Humans click "Merge" in SUTRA UI -> SUTRA calls GitHub Merge API using App credentials. | GitHub Native Merge (Humans click merge on github.com; SUTRA observes via webhook). |

---

*Phase 2 Target Architecture Specification Complete.*
