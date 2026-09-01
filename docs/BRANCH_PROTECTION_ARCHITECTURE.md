# SUTRA — Branch Protection & Merge Gates Architecture (v0.3.3)

## Overview
This document defines the architectural specification for SUTRA's Branch Protection & Merge Gates system. Branch protection acts as a **policy configuration layer** built around repositories and target branches. It evaluates rules against Pull Requests before allowing them to reach `merge_ready` state in merge orchestration.

---

## Architectural Hierarchy & Component Model

```
POST /v1/pull-requests/{id}/merge
           │
           ▼
     PullRequestService.orchestrate_merge
     ├── 1. Acquire PostgreSQL Row Lock (.with_for_update())
     ├── 2. Validate PR Status (must be 'open' or 'approved')
     ├── 3. Evaluate BranchProtectionService.evaluate_pull_request(pr)
     │     ├── Match effective BranchProtectionRule for pr.target_branch
     │     ├── Check required_approvals against valid ChangeReview records
     │     ├── Check author self-approval prohibition
     │     ├── Check unresolved InlineReviewComment threads
     │     ├── Check AgentReview findings (if configured)
     │     └── Check ConflictService status (must be 'none')
     ├── 4. Evaluate ChangePolicyService (must be ALLOW)
     └── 5. Return status="merge_ready" (HTTP 200) WITHOUT ref mutation
```

---

## Authoritative Boundaries & Principles

1. **Policy Configuration Layer Only**: Branch Protection defines branch-level requirement rules (`required_approvals`, `require_resolved_threads`, etc.). It does **NOT** replace `ChangePolicyService`, `ChangeReview`, `ConflictService`, or `AuthorizationService`.
2. **Approval Authority**: `ChangeReview` remains the **SOLE** approval mechanism in SUTRA. Branch protection counts non-author, non-actor approved `ChangeReview` records.
3. **Agent Review Boundary**: Agent findings and comments are analyzed during gate evaluation if `require_no_blocking_agent_findings` is enabled. Agents do NOT manufacture `ChangeReview` approvals.
4. **Merge Orchestration Boundary**: Merging returns `{ "status": "merge_ready" }` upon passing all gates. No fake Git merges or ref mutations take place.

---

## Data Model (`branch_protection_rules`)

- `id`: `String(36)` Primary Key (UUIDv4)
- `repository_id`: `String(36)` Foreign Key -> `repositories.id` (ON DELETE CASCADE, Index)
- `branch_pattern`: `String(255)` Non-null (e.g. `'main'`, `'release/*'`, `'*'`)
- `enabled`: `Boolean` Non-null default `True`
- `required_approvals`: `Integer` Non-null default `1`
- `require_change_review`: `Boolean` Non-null default `True`
- `require_clean_conflict`: `Boolean` Non-null default `True`
- `require_resolved_threads`: `Boolean` Non-null default `True`
- `require_agent_review`: `Boolean` Non-null default `False`
- `require_no_blocking_agent_findings`: `Boolean` Non-null default `False`
- `allow_author_self_approval`: `Boolean` Non-null default `False`
- `created_by`: `String(36)` Foreign Key -> `users.id` (ON DELETE RESTRICT)
- `updated_by`: `String(36)` Foreign Key -> `users.id` (ON DELETE RESTRICT)
- `created_at`: `DateTime(timezone=True)` Non-null
- `updated_at`: `DateTime(timezone=True)` Non-null

### Constraints
- `UNIQUE(repository_id, branch_pattern)`
- `CHECK(required_approvals >= 0)`

---

## Branch Matching Semantics

- Exact match takes highest precedence (e.g. `target_branch == 'main'`).
- Wildcard match using `fnmatch.fnmatch` (e.g. `release/*`, `feature/*`).
- Default wildcard `*` matches any branch if no exact/pattern rule exists.

---

## Known Limitations

1. **No Safe Server-Side Git Merge Transport**: Merge endpoint returns status `merge_ready` when all branch protection and policy gates pass. No local Git refs are mutated.
2. **Configuration Scope**: Protection rules apply to Pull Request target branches; they do not alter bare Git push policy directly (which is handled by `GitReceivePolicyService`).
