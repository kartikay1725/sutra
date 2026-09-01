# SUTRA — Task / Issue System & Agent Task Execution Architecture (v0.3.5)

## Overview
This document specifies the architectural model for SUTRA's Task / Issue System & Agent Task Execution Workflow (v0.3.5). The Task layer turns SUTRA into an AI-native engineering platform where a task can be assigned to human engineers or autonomous agents, executed inside isolated container sandboxes to produce a `Change`, linked to a `PullRequest`, verified by `CIJob`, evaluated by `BranchProtectionRule`, and merged through the safe merge boundary.

---

## Authoritative Hierarchy

```
Issue / Task (WHAT needs to be done)
       │
       ▼
Task Assignment (Human User or Authorized Agent)
       │
       ▼
Agent Task Execution (CISandbox Container Sandbox - Classification A)
       │
       ▼
Change (WHAT code actually changed - Authoritative)
       │
       ▼
PullRequest (PR Lifecycle - Authoritative)
       │
       ▼
Inline Review Comments & Agent Review Summary
       │
       ▼
CI Verification (CIJob - Exact commit SHA matching)
       │
       ▼
Branch Protection / Merge Gates (BranchProtectionService)
       │
       ▼
SAFE MERGE BOUNDARY (status="merge_ready")
```

---

## Architectural Principles & Non-Bypass Invariants

1. **Orchestration Layer Only**: The Task system orchestrates work units and tracks progress. It does **NOT** replace `Change`, `ChangeReview`, `PullRequest`, `ChangePolicyService`, `ConflictService`, `AuthorizationService`, `BranchProtectionService`, or `CIService`.
2. **Authoritative Subsystems**:
   - `Change` remains sole authority for code mutations & commit SHAs.
   - `ChangeReview` remains sole authority for code approvals.
   - `PullRequest` remains sole authority for PR lifecycle and status.
   - `AuthorizationService` remains sole authority for access control.
3. **Execution Sandbox Boundary**: Agent task execution MUST NOT execute host process commands. All automated agent execution runs inside `CISandbox` (ephemeral OCI container, `--network=none`, non-root `--user 1000:1000`, `--cap-drop=ALL`, CPU/RAM caps).
4. **Safe Merge Boundary**: A completed Task/PR workflow resolves to `status="merge_ready"`. No direct server-side Git ref mutations or fake merges take place.

---

## Data Model Specification (`tasks`)

- `id`: `String(36)` Primary Key (UUIDv4)
- `repository_id`: `String(36)` Foreign Key -> `repositories.id` (ON DELETE CASCADE, Index)
- `created_by`: `String(36)` Foreign Key -> `users.id` (ON DELETE RESTRICT, Index)
- `assigned_agent_id`: `String(36)` Nullable Foreign Key -> `agents.id` (ON DELETE RESTRICT, Index)
- `assigned_user_id`: `String(36)` Nullable Foreign Key -> `users.id` (ON DELETE RESTRICT, Index)
- `resulting_change_id`: `String(36)` Nullable Foreign Key -> `changes.id` (ON DELETE SET NULL, Index)
- `resulting_pull_request_id`: `String(36)` Nullable Foreign Key -> `pull_requests.id` (ON DELETE SET NULL, Index)
- `title`: `String(255)` Non-null
- `description`: `Text` Nullable
- `status`: `String(30)` Non-null default `'open'` (CheckConstraint: `status IN ('open', 'assigned', 'in_progress', 'blocked', 'completed', 'cancelled')`)
- `priority`: `String(20)` Non-null default `'medium'` (CheckConstraint: `priority IN ('low', 'medium', 'high', 'critical')`)
- `task_type`: `String(30)` Non-null default `'feature'` (CheckConstraint: `task_type IN ('feature', 'bugfix', 'refactor', 'security', 'documentation')`)
- `source`: `String(30)` Non-null default `'user'`
- `created_at`: `DateTime(timezone=True)` Non-null
- `updated_at`: `DateTime(timezone=True)` Non-null
- `started_at`: `DateTime(timezone=True)` Nullable
- `completed_at`: `DateTime(timezone=True)` Nullable
- `cancelled_at`: `DateTime(timezone=True)` Nullable
