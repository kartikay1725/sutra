# SUTRA — Inline Code Review API Reference (v0.3)

This document specifies the REST API endpoints provided by the Inline Code Review Platform.

---

## Endpoint Summary Matrix

| Method | Endpoint | Description | Authorization |
| :--- | :--- | :--- | :--- |
| `GET` | `/v1/pull-requests/{id}/diff` | Get parsed diff hunks and line metadata | Repository Read |
| `GET` | `/v1/pull-requests/{id}/files` | Get changed files list for PR | Repository Read |
| `GET` | `/v1/pull-requests/{id}/comments` | List all review comments & threads for PR | Repository Read |
| `POST` | `/v1/pull-requests/{id}/comments` | Create general or inline review comment | Repository Read/Write |
| `POST` | `/v1/pull-requests/{id}/comments/{comment_id}/reply` | Reply to an existing comment thread | Repository Read/Write |
| `POST` | `/v1/pull-requests/{id}/comments/{comment_id}/resolve` | Resolve an active review thread | Repository Read/Write |
| `POST` | `/v1/pull-requests/{id}/comments/{comment_id}/reopen` | Reopen a resolved review thread | Repository Read/Write |

---

## Request & Response Schemas

### InlineCommentCreateRequest
```json
{
  "body": "Fix variable naming convention here.",
  "path": "backend/app/main.py",
  "diff_side": "RIGHT",
  "line_number": 42,
  "commit_sha": "1111111111111111111111111111111111111111",
  "parent_id": null
}
```

### InlineCommentReplyRequest
```json
{
  "body": "Updated in latest commit."
}
```

### InlineCommentResponse
```json
{
  "id": "e9cd867b-5905-4c95-92ba-0b05941b7354",
  "pull_request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "repository_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "author_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
  "parent_id": null,
  "path": "backend/app/main.py",
  "diff_side": "RIGHT",
  "line_number": 42,
  "line_range_start": null,
  "line_range_end": null,
  "commit_sha": "1111111111111111111111111111111111111111",
  "body": "Fix variable naming convention here.",
  "status": "active",
  "created_at": "2026-08-14T18:15:00Z",
  "updated_at": "2026-08-14T18:15:00Z",
  "resolved_at": null,
  "resolved_by": null
}
```
