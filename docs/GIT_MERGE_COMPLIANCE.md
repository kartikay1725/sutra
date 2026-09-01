# SUTRA Phase 22 — Git Merge Compliance & Audit Trail

## Executive Overview
SUTRA v0.3.6 enforces full audit trail logging and audit event generation for all server-side Git merge operations.

---

## Audit Trail Invariants

1. **`pull_request.merged` Event Emission**:
   - Recorded in `change_events` table upon verified merge completion.
   - Contains metadata: `source_commit`, `previous_target_commit`, `resulting_commit`, `is_fast_forward`, and `target_branch`.

2. **Linked Task State Completion**:
   - Any `Task` whose `resulting_pull_request_id` equals the merged PR ID transitions from `in_progress` to `completed`.
   - `completed_at` timestamp is set atomically within the database transaction.

3. **Immutability of Merged State**:
   - A `merged` PR cannot be re-opened, re-approved, or re-merged.
   - Idempotent invocation returns HTTP 200 with status `"merged"`.
