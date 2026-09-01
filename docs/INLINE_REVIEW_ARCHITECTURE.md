# SUTRA — Inline Code Review Architecture & Integration Guide (v0.3)

## Overview
This document defines the architectural specification for SUTRA's Inline Code Review Platform. Inline review functionality operates as a discussion and review feedback layer positioned above the SUTRA Pull Request Platform (v0.3.1) and underlying `Change` / `ChangeReview` architecture.

---

## Architectural Hierarchy & Data Flow

```
Git Transport (HTTP receive-pack)
           │
           ▼
     GitPushEvent Queue
           │
           ▼
      Change Model (Authoritative Code Operation)
     ├── ChangeFile, ChangeEvent
     └── Status: proposed | recorded | blocked | rejected
           │
           ├── Policy Evaluation (ChangePolicyService)
           ├── Conflict Analysis (ConflictService)
           └── Capability Checks (AuthorizationService)
           │
           ├── ChangeReview (Sole Authoritative Approval Mechanism)
           │     └── Status: pending | approved | rejected
           │
           ▼
      PullRequest Model (Management Abstraction)
           │
           ▼
      Inline Code Review Platform (Phase 17)
     ├── Unified Git Diff Engine (Commit-anchored diffs & hunks)
     ├── Inline & General PR Review Comments (inline_review_comments)
     ├── Threading (parent_id hierarchy for replies)
     ├── Thread Resolution & Reopening Mechanics
     └── Transactional Audit Events (ChangeEvent)
```

---

## Authoritative Boundaries & Principles

1. **Sole Approval Authority**: `ChangeReview` remains the **ONLY** authoritative mechanism for approvals in SUTRA. Inline comments and thread resolution are discussion artifacts and cannot approve a Change or Pull Request.
2. **Policy & Authorization Boundary**: Creation of comments, replies, and resolution requires explicit authorization verification via `AuthorizationService` for the target repository. `ChangePolicyService` blocks operate independently.
3. **Change & Code Operation Invariant**: Diff generation derives strictly from the `Change` commits (`base_commit` to `resulting_commit`) via bare Git repository inspection.
4. **Audit Atomicity**: All inline review actions emit `ChangeEvent` audit entries in the same database transaction, maintaining transactional integrity.

---

## Persistence Model (`inline_review_comments`)

- `id`: `String(36)` Primary Key (UUIDv4)
- `pull_request_id`: `String(36)` Foreign Key -> `pull_requests.id` (ON DELETE CASCADE, Index)
- `repository_id`: `String(36)` Foreign Key -> `repositories.id` (ON DELETE CASCADE, Index)
- `author_id`: `String(36)` Foreign Key -> `users.id` (ON DELETE RESTRICT, Index)
- `parent_id`: `String(36)` Nullable Foreign Key -> `inline_review_comments.id` (ON DELETE CASCADE, Index)
- `path`: `String(1000)` Nullable (File path for inline comments; NULL for general PR comments)
- `diff_side`: `String(10)` Nullable (`'LEFT'` / `'RIGHT'`, or NULL for general PR comments)
- `line_number`: `Integer` Nullable (Line number in the diff/file; NULL for general PR comments)
- `line_range_start`: `Integer` Nullable
- `line_range_end`: `Integer` Nullable
- `commit_sha`: `String(64)` Nullable (Target commit SHA for anchoring)
- `body`: `Text` Non-null (Comment body)
- `status`: `String(30)` Non-null default `'active'` (`'active'`, `'resolved'`)
- `created_at`: `DateTime(timezone=True)` Non-null
- `updated_at`: `DateTime(timezone=True)` Non-null
- `resolved_at`: `DateTime(timezone=True)` Nullable
- `resolved_by`: `String(36)` Nullable Foreign Key -> `users.id` (ON DELETE SET NULL)

### Database Constraints
- **CHECK Constraint**: `status IN ('active', 'resolved')`
- **CHECK Constraint**: `diff_side IS NULL OR diff_side IN ('LEFT', 'RIGHT')`

---

## Line Anchoring Strategy

1. **Commit Anchoring**: Inline comments store `commit_sha` (the source/resulting commit against which the comment was created) along with `path`, `diff_side`, and `line_number`.
2. **Diff Verification**: Service layer verifies that `path` exists in the `ChangeFile` set for the PR and that `line_number` is a positive integer within valid file bounds.
3. **General PR Comments**: Created with `path=None`, `line_number=None`, `diff_side=None`.

---

## Known Limitations

1. **No Safe Server-Side Git Merge Transport**: `POST /v1/pull-requests/{id}/merge` remains a guarded orchestration endpoint returning `status="merge_ready"`. Inline review comments do not trigger ref mutations or fake Git merges.
2. **Discussion Non-Approval**: Resolving all inline review threads does not bypass required `ChangeReview` approvals or `ChangePolicyService` rules.
