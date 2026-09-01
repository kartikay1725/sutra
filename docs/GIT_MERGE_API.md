# SUTRA Phase 22 — Git Merge Transport API Specification

## Executive Overview
SUTRA v0.3.6 replaces synthetic/dummy merge responses with real, verified server-side Git merge operations executing directly against bare repositories stored on disk.

---

## 1. Primary Service Interface

### `GitMergeService.execute_server_side_merge`

```python
def execute_server_side_merge(
    self,
    repository_storage_key: str,
    target_branch: str,
    source_commit: str,
    merger_id: str,
    commit_message: str = "Merge commit by SUTRA Server-Side Transport",
) -> GitMergeResult
```

### Return Contract (`GitMergeResult`)
- `success`: `bool` — True if ref update is verified on disk.
- `resulting_commit`: `str` — 40-character hex SHA of the merge commit.
- `target_branch`: `str` — Name of target branch updated.
- `previous_target_commit`: `str` — 40-character hex SHA of previous target ref.
- `is_fast_forward`: `bool` — True if fast-forward strategy was used.

---

## 2. API Flow & Precondition Gate Sequence

1. **PullRequest Status Check**: PR must be in `open` or `approved` status.
2. **Authorization Gate**: User/Agent must have repository write capability.
3. **ChangePolicy Gate**: Authoritative policy evaluation must pass.
4. **ChangeReview Gate**: Approved review by non-author required.
5. **Conflict Gate**: Zero git merge conflict.
6. **Branch Protection Gate**: All branch rules satisfied.
7. **Git Transport Execution**: `GitMergeService` executes atomic Compare-and-Swap ref update.
8. **DB Transaction**: `PullRequest.status = 'merged'`, `pr.merged_at = now()`, `ChangeEvent(pull_request.merged)` recorded, linked `Task.status = 'completed'`.
