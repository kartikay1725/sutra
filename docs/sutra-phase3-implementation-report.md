# SUTRA Phase 3 Implementation Report: Control-Plane & Provider Abstraction

**Phase:** 3 — Provider Layer & GitHub Integration Implementation  
**Date:** 2026-08-31  
**Status:** Complete & Fully Tested (All 10 Phase 3 unit, security, and E2E lifecycle tests passing)

---

## 1. Executive Summary

Phase 3 implements the substrate provider abstraction for SUTRA, integrating GitHub as the first external repository substrate while preserving the local bare Git provider.

### Core Directives Enforced:
1. **Isolated Responsibilities:** `RepositoryProvider` (substrate repo operations), `CredentialProvider` (downstream token broker), `WebhookEventAdapter` (signature & event normalizer), and `CheckProvider` / `CheckService` (status check publishing) are completely separated.
2. **SUTRA Sovereignty:** SUTRA `AgentSession` remains the primary agent identity. Downstream tokens are transport-only credentials with **effective TTL $\le$ 10 minutes** and zero merge capability.
3. **Push vs. Merge Semantics:** Feature branch pushes may arrive at GitHub before SUTRA policy evaluation, but SUTRA publishes blocking Check Runs and refuses PR mergeability until all SUTRA policy and human review gates pass.
4. **No Code Deletions:** The local Git provider was completely retained and wrapped under `LocalRepositoryProvider`, ensuring zero regression.

---

## 2. Files Created

| File Path | Component | Responsibility |
|-----------|-----------|----------------|
| `backend/app/providers/__init__.py` | Provider Core | Module export definitions. |
| `backend/app/providers/base.py` | `RepositoryProvider` | Substrate interface for branch, commit, diff, file, PR, and merge operations (check-run operations removed per amendment). |
| `backend/app/providers/credentials.py` | `CredentialProvider` | Interface for downstream token issuance and active revocation. |
| `backend/app/providers/events.py` | `WebhookEventAdapter` | Webhook signature verification and domain event normalization (`NormalizedPushEvent`, `NormalizedPullRequestEvent`). |
| `backend/app/providers/checks.py` | `CheckProvider` | Interface for publishing/updating status checks and Check Runs. |
| `backend/app/providers/registry.py` | `ProviderRegistry` | Dynamically resolves provider implementations by repository `provider_type`. |
| `backend/app/providers/local/__init__.py` | Local Provider | Package exports. |
| `backend/app/providers/local/repository.py` | `LocalRepositoryProvider` | Substrate adapter for local bare Git repositories and `GitMergeService`. |
| `backend/app/providers/local/credentials.py` | `LocalCredentialProvider` | Issues and revokes local Git HTTP Basic Auth credentials. |
| `backend/app/providers/local/checks.py` | `LocalCheckProvider` | Local check runner and policy decision tracker. |
| `backend/app/providers/local/events.py` | `LocalWebhookAdapter` | Local event simulation adapter. |
| `backend/app/providers/github/__init__.py` | GitHub Provider | Package exports. |
| `backend/app/providers/github/auth.py` | `GitHubAppAuthService` | GitHub App RS256 JWT generator and installation token negotiator. |
| `backend/app/providers/github/repository.py` | `GitHubRepositoryProvider` | Full GitHub REST API substrate adapter (branches, commits, diffs, PRs, merge API). |
| `backend/app/providers/github/credentials.py` | `GitHubCredentialProvider` | Downstream token broker with effective 10-minute maximum lifespan, capability mapping, and Redis tracking. |
| `backend/app/providers/github/checks.py` | `GitHubCheckProvider` | Publishes Check Runs to GitHub Check Runs API (`POST /repos/{owner}/{name}/check-runs`). |
| `backend/app/providers/github/events.py` | `GitHubWebhookAdapter` | HMAC-SHA256 signature verification and GitHub payload normalizer. |
| `backend/app/services/check_service.py` | `CheckService` | Bridges `ChangePolicyService` and human review status to Check Runs. |
| `backend/app/api/webhooks/github.py` | Webhooks API | Endpoint `POST /v1/webhooks/github` for secure webhook ingestion and `GitPushEvent` generation. |
| `backend/tests/test_local_provider.py` | Test Suite | Unit tests for local provider and registry resolution. |
| `backend/tests/test_github_security.py` | Test Suite | Security assertion tests for tokens, capability mapping, and untracked push mergeability blocking. |
| `backend/tests/test_github_lifecycle_e2e.py` | Test Suite | Full end-to-end integration test spanning registration, token broker, push webhook, change, review approval, check runs, and GitHub merge. |

---

## 3. Files Modified

| File Path | Modifications Made |
|-----------|-------------------|
| `backend/app/api/repositories.py` | Added `POST /v1/repositories/{owner}/{repo}/token` endpoint for agent downstream transport token issuance with capability checks. |
| `backend/app/main.py` | Registered `webhooks_router` (`POST /v1/webhooks/github`). |

---

## 4. Tests Added & Verification Results

All 10 tests across the test suite execute and pass:

```
tests/test_local_provider.py::test_provider_registry_resolution PASSED
tests/test_local_provider.py::test_local_repository_metadata PASSED
tests/test_local_provider.py::test_local_credential_issuance_and_revocation PASSED
tests/test_local_provider.py::test_local_check_provider PASSED
tests/test_github_security.py::test_github_app_jwt_generation PASSED
tests/test_github_security.py::test_minimal_capability_mapping_no_merge_rights PASSED
tests/test_github_security.py::test_effective_max_ttl_bounded_to_10_minutes PASSED
tests/test_github_security.py::test_active_downstream_token_revocation PASSED
tests/test_github_security.py::test_untracked_feature_push_cannot_become_mergeable PASSED
tests/test_github_lifecycle_e2e.py::test_complete_github_lifecycle_e2e PASSED

======================= 10 passed, 3 warnings in 5.91s ========================
```

---

## 5. Security Invariants Verified

1. **Primary Agent Identity Invariant:** SUTRA `AgentSession` is sovereign. Downstream GitHub tokens cannot authenticate to SUTRA REST APIs.
2. **Minimal Capability Mapping:** `repository.write` strictly maps to `contents:write`. It does NOT grant `pull_requests:write` or merge capabilities to agent tokens.
3. **Effective 10-Minute Maximum TTL:** Downstream tokens are bounded to $\le 600\text{s}$ in SUTRA. Re-use or renewal is refused beyond this boundary.
4. **Active Downstream Revocation:** SUTRA session revocation triggers asynchronous `DELETE /installation/token` to invalidate the downstream token on GitHub immediately.
5. **Untracked / Unauthorized Push Containment:** Feature branch pushes arriving at GitHub before SUTRA evaluation cannot bypass policy. SUTRA reports a `FAILURE` Check Run and blocks mergeability.
6. **Separation of Approval & Merge Authority:** An agent cannot approve its own review or trigger PR merge. Merge authority requires Human JWT and distinct reviewer approval (`requested_by != reviewer_id`).

---

## 6. Provider Boundaries Verified

- **SUTRA Core Services:** `AuthorizationService`, `ChangePolicyService`, `PullRequestService`, `BranchProtectionService`, `TaskService`, `AuditService` have zero GitHub-specific dependencies.
- **Provider Layer Isolation:** All GitHub REST API calls and token negotiations reside strictly within `app.providers.github.*`.
- **Dual-Provider Architecture:** `ProviderRegistry` seamlessly dispatches requests to `LocalRepositoryProvider` or `GitHubRepositoryProvider` based on `Repository.provider_type`.

---

## 7. Code Intentionally Retained

- `backend/app/services/repository_service.py` (Local bare repository initialization)
- `backend/app/services/git_merge_service.py` (Local CAS server-side git merge)
- `backend/app/services/repository_browser_service.py` (Local bare git file reading)
- `backend/app/git_pre_receive.py` (Local pre-receive policy hook)
- All existing models (`Agent`, `Actor`, `AgentSession`, `AgentRepositoryAccess`, `Change`, `PullRequest`, `Task`)

---

## 8. Remaining Risks & Phase 4 Preparation

| Risk Area | Mitigation in Place | Next Phase Action |
|-----------|---------------------|-------------------|
| GitHub Webhook Latency / Drop | `POST /v1/webhooks/github` handles push events asynchronously; out-of-band polling reconciliation will run in background worker. | Phase 4: Add periodic out-of-band PR reconciliation task to `SessionReaperWorker`. |
| GitHub Plan Tier Differences | Capability detection in `GitHubRepositoryProvider.get_repository_metadata` detects ruleset support vs classic branch protection. | Phase 4: Provide UI indicator in repository settings showing detected GitHub plan capabilities. |
| Private Key Storage | `GitHubAppAuthService` loads PEM string from environment settings or secrets manager without persisting to DB. | Phase 4: Add configuration validation on application startup. |

---

*Phase 3 implementation complete and verified.*
