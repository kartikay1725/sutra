# SUTRA — CI Runner & Automated Verification Platform Architecture (v0.3.4)

## Overview
This document defines the architectural specification for SUTRA's CI Runner & Automated Verification Platform (v0.3.4). CI provides automated build, lint, test, and security verification for Pull Requests without acting as an approval authority or modifying Git refs.

---

## Architectural Position

```
GitPushEvent / API Trigger
           │
           ▼
     PullRequest / Change
           │
           ▼
     CIService.create_job(pull_request_id, commit_sha, trigger)
           │
           ▼
     CIJob (status="queued")
           │
           ▼
     CIRunner (Isolated Execution Boundary)
     ├── Acquire PostgreSQL Row Lock (.with_for_update())
     ├── Transition status="running", assign worker_id & lease_expires_at
     ├── Create Isolated Workspace (scratch/ci_workspaces/{job_id})
     ├── Strip Host Environment & Secrets (DATABASE_URL, SECRET_KEY, tokens)
     ├── Execute Verification Steps with Resource & Timeout Limits
     ├── Bounded Output & Exit Code Capture
     ├── Clean Workspace
     └── Transition status="passed" | "failed" | "timed_out" | "cancelled"
           │
           ▼
     BranchProtectionService (require_ci_passed gate evaluation)
           │
           ▼
     PullRequestService.merge_pull_request (status="merge_ready")
```

---

## Invariants & Authoritative Boundaries

1. **Verification System Only**: CI establishes whether automated verification checks passed for a specific commit SHA. CI is **NOT** an approval authority and cannot set `ChangeReview.status` to `approved` or bypass `ChangePolicyService`.
2. **Commit-Specific Gate**: `BranchProtectionService` checks that CI for the **exact authoritative commit SHA** of the Pull Request has passed. CI for commit A cannot satisfy branch protection for commit B.
3. **Execution Boundary & Secret Isolation**:
   - Environment variables (`DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, agent tokens, passwords) are **NEVER** passed into CI worker processes.
   - Workspace directories are isolated per job in temporary scratch locations and cleaned up immediately after execution.
   - Commands use explicit list args (`shell=False`), timeout limits, output size caps, and strict path validation to prevent shell/command injection or directory traversal.
4. **No Direct Ref Mutation**: CI execution does not mutate local Git refs, set `merged_at`, or alter `PullRequest.status` to `merged`.

---

## Data Model (`ci_jobs`)

- `id`: `String(36)` Primary Key (UUIDv4)
- `pull_request_id`: `String(36)` Foreign Key -> `pull_requests.id` (ON DELETE CASCADE, Index)
- `repository_id`: `String(36)` Foreign Key -> `repositories.id` (ON DELETE CASCADE, Index)
- `change_id`: `String(36)` Foreign Key -> `changes.id` (ON DELETE CASCADE, Index)
- `commit_sha`: `String(64)` Non-null (Index)
- `target_branch`: `String(255)` Non-null
- `status`: `String(30)` Non-null default `'queued'` (CheckConstraint: `status IN ('queued', 'running', 'passed', 'failed', 'cancelled', 'timed_out')`)
- `trigger`: `String(50)` Non-null default `'pull_request'`
- `runner_type`: `String(50)` Non-null default `'isolated_process'`
- `exit_code`: `Integer` Nullable
- `failure_reason`: `Text` Nullable
- `output_log`: `Text` Nullable
- `worker_id`: `String(64)` Nullable (Index)
- `lease_expires_at`: `DateTime(timezone=True)` Nullable (Index)
- `started_at`: `DateTime(timezone=True)` Nullable
- `completed_at`: `DateTime(timezone=True)` Nullable
- `cancelled_at`: `DateTime(timezone=True)` Nullable
- `created_at`: `DateTime(timezone=True)` Non-null
- `updated_at`: `DateTime(timezone=True)` Non-null

---

## Security Audit & Vulnerability Controls

- **IDOR / BOLA**: Endpoint authorizations verify user access to private repositories. Non-collaborators receive HTTP 404.
- **Environment Isolation**: Strip all host environment keys before spawning verification processes.
- **Path Traversal Protection**: Reject workspace paths containing `..` or leading `/`.
- **Command Injection Protection**: Reject shell metacharacters and execute using explicit argv arrays (`shell=False`).
