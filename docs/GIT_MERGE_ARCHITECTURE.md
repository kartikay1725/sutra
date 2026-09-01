# SUTRA — Safe Server-Side Git Merge Transport Architecture (v0.3.6)

## Overview
This document specifies the server-side Git merge transport architecture for SUTRA v0.3.6. It establishes a real, atomic, compare-and-swap (CAS) Git merge transport to transition Pull Requests to `status = "merged"`.

---

## Architectural Workflow

```
PullRequest (status="approved" or "open")
       │
       ▼
PullRequestService.merge_pull_request() [Row Lock: with_for_update()]
       │
       ▼
Precondition Checks (Auth, Policy, Review, CI, Branch Protection, Conflict)
       │
       ▼
GitMergeService.merge()
       │
       ├─► 1. Resolve Target Branch Ref (refs/heads/<target_branch>) -> expected_target_sha
       ├─► 2. Validate Source Commit SHA (PR.source_commit / Change.resulting_commit) -> source_commit_sha
       ├─► 3. Compute Merge Base (git merge-base) & Check Relation
       ├─► 4. Compute Merged Tree (git merge-tree or isolated index commit creation)
       ├─► 5. Create Merge Commit (git commit-tree -p expected_target_sha -p source_commit_sha)
       ├─► 6. ATOMIC CAS REF UPDATE:
       │      git update-ref refs/heads/<target_branch> new_merge_sha expected_target_sha
       │      (Fails atomically if target branch was updated concurrently)
       └─► 7. Post-Update Ref Verification (git rev-parse)
       │
       ▼
PostgreSQL Transaction Finalization
       │
       ├─► PR.status = "merged", PR.merged_at = now()
       ├─► Audit Event: pull_request.merged
       └─► Linked Task: Task.status = "completed" (if applicable)
```

---

## Invariants & Security Guarantees

1. **Compare-and-Swap (CAS) Ref Mutation**:
   - `git update-ref refs/heads/<branch> <new_sha> <old_sha>` enforces that `<branch>` is updated ONLY if it currently equals `<old_sha>`.
   - If a concurrent push or merge occurred, `git update-ref` returns non-zero error, aborting the merge with `HTTP 409 Conflict`.
2. **Subprocess Security**:
   - All Git commands execute via explicit `argv` arrays with `shell=False`.
   - Strict validation of repository path, branch name regex, and 40-character hex SHA strings. No user input interpolation into shell commands.
3. **Database / Git Consistency Model**:
   - Git ref update occurs within the service boundary.
   - Post-update verification ensures target ref equals `new_merge_sha`.
   - `PullRequest.status` becomes `"merged"` ONLY after target ref update is verified.
4. **Task Lifecycle Integration**:
   - Linked `Task` becomes `"completed"` ONLY after verified Git ref update and PR transition to `"merged"`.
