# SUTRA Phase 22 — Git Merge Security Audit & Controls

## Executive Overview
This document specifies the security controls, boundary invariants, and isolation mechanisms enforced by `GitMergeService` during server-side Git merge operations.

---

## Security Invariants

### 1. Argument Sanitization & Subprocess Isolation
- **`shell=False` Execution**: All Git command invocations use explicit Python lists (argv).
- **Ref Name Validation**: Branch names are validated against regex `^[a-zA-Z0-9_\-\./]+$`. Traversal patterns (`..`, leading/trailing `/`) are rejected.
- **Commit SHA Validation**: Commit SHAs are strictly validated against `^[0-9a-fA-F]{40}$`.

### 2. Compare-and-Swap (CAS) Ref Update Atomicity
- Ref updates are executed via `git update-ref refs/heads/<branch> <new_sha> <expected_sha>`.
- If a target branch moves prior to ref update execution, `update-ref` fails with a non-zero exit code, triggering HTTP 409 Conflict.
- Zero ref corruption occurs under high-concurrency race conditions.

### 3. Post-Update Ref Verification
- After `update-ref` completes, `GitMergeService` re-reads `git rev-parse refs/heads/<target_branch>` from disk and asserts exact equality with `<new_sha>`.
- `PullRequest.status` and linked `Task.status` transition to `merged` and `completed` ONLY after disk verification passes.
