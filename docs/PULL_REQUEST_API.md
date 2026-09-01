# SUTRA — Pull Request API Specifications

## 1. REST API Endpoints

### 1.1 `POST /v1/pull-requests`
Creates a Pull Request from a source change.
- **Request Body**:
  ```json
  {
    "repository_id": "UUID",
    "source_change_id": "UUID",
    "title": "Title String",
    "description": "Optional Description",
    "target_branch": "main",
    "is_draft": false
  }
  ```
- **Returns**: `201 Created` with PR model, `403 Forbidden` (Unauth), `409 Conflict` (Duplicate source_change_id or cross-repository change).

### 1.2 `GET /v1/pull-requests`
Lists Pull Requests matching the optional query filters.
- **Filters**: `repository_id`, `status`, `author_id`.
- **Returns**: `200 OK` with list of PRs.

### 1.3 `GET /v1/pull-requests/{pull_request_id}`
Retrieves a Pull Request by UUID.
- **Returns**: `200 OK` with PR model, `404 Not Found`.

### 1.4 `GET /v1/pull-requests/{pull_request_id}/changes`
Retrieves the underlying Change resource for the PR.
- **Returns**: `200 OK` with Change model, `404 Not Found`.

### 1.5 `GET /v1/pull-requests/{pull_request_id}/reviews`
Retrieves reviews from SUTRA's authoritative `ChangeReview` system.
- **Returns**: `200 OK` with list of reviews, `404 Not Found`.

### 1.6 `GET /v1/pull-requests/{pull_request_id}/conflicts`
Retrieves conflict results from SUTRA's authoritative `ConflictService`.
- **Returns**: `200 OK` with ConflictResult, `404 Not Found`.

### 1.7 `GET /v1/pull-requests/{pull_request_id}/events`
Retrieves PR transition audit events.
- **Returns**: `200 OK` with list of events, `404 Not Found`.

### 1.8 `POST /v1/pull-requests/{pull_request_id}/approve`
Approves the PR. Requires non-author, non-actor `ChangeReview` approval.
- **Returns**: `200 OK` with updated PR model, `409 Conflict` on invalid transition.

### 1.9 `POST /v1/pull-requests/{pull_request_id}/reject`
Rejects the PR.
- **Returns**: `200 OK` with updated PR model.

### 1.10 `POST /v1/pull-requests/{pull_request_id}/close`
Closes the PR.
- **Returns**: `200 OK` with PR model.

### 1.11 `POST /v1/pull-requests/{pull_request_id}/merge`
Guarded merge orchestration check.
- **Preconditions Checked**: Policy evaluate, approved review exists, conflict status is none.
- **Returns**: `200 OK` with `{ "status": "merge_ready" }`.
- **Limitation**: Does **NOT** execute actual Git ref merge or set status to `merged`.
