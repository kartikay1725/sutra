# SUTRA — Pull Request Architecture & API Reference

> **Version**: 0.4.0 (Beta)  
> **Source of Truth**: Reflects the current SUTRA Control Plane and GitHub Substrate integration.

---

## 1. Overview & Architectural Role

In SUTRA, the **Pull Request** is the bridge between SUTRA's high-level governance and the external Git code substrate (GitHub).

- **GitHub** provides the physical pull request container (head branch, base branch, line diffs, check runs, merge commit).
- **SUTRA** provides the authoritative governance container (originating Task, AgentSession provenance, 4-pillar policy verdict, human review gate, governed merge authorization).

---

## 2. REST API Endpoints

### 2.1 `POST /v1/pull-requests`
Creates a Pull Request linking a SUTRA Change to an external substrate PR.
- **Caller**: Human User (`Authorization: Bearer <HUMAN_JWT>`) or Agent (`Authorization: Bearer <AGENT_SESSION_TOKEN>`)
- **Request Body**:
  ```json
  {
    "repository_id": "UUID",
    "source_change_id": "UUID",
    "title": "feat: implement feature X",
    "description": "Optional description",
    "target_branch": "main",
    "is_draft": false
  }
  ```
- **Returns**: `201 Created` with enriched `PullRequestResponse`.

### 2.2 `GET /v1/pull-requests`
Lists Pull Requests matching query filters (`repository_id`, `status`, `author_id`).
- **Returns**: `200 OK` with list of `PullRequestResponse`.

### 2.3 `GET /v1/pull-requests/{id}`
Retrieves a Pull Request by UUID, enriched with live CI check summaries and governance verdict.
- **Returns**: `200 OK` with `PullRequestResponse`.

### 2.4 `GET /v1/pull-requests/{id}/checks`
Retrieves live CI check run details and overall status ingested from GitHub webhooks.
- **Returns**: `200 OK` with `PRChecksResponse`.

### 2.5 `GET /v1/pull-requests/{id}/governance`
Evaluates the 4-pillar governance status for the pull request:
1. **Checks & CI**: Required automated checks passed on the exact HEAD commit SHA.
2. **Provenance**: Verified AgentSession or Human authorship.
3. **Policy & Conflict**: File overlap and sensitive file policy evaluation.
4. **Review Requirements**: Valid human approvals recorded.
- **Returns**: `200 OK` with `GovernanceEvaluationResponse`.

### 2.6 `POST /v1/pull-requests/{id}/approve`
Human approval gate.
- **Requirements**:
  - Caller must be an authenticated Human user (`Authorization: Bearer <HUMAN_JWT>`).
  - Caller must NOT be the author or requesting agent (`reviewer_id != requester_id`).
  - Approval is cryptographically bound to the current HEAD commit SHA.
- **Returns**: `200 OK` with updated `PullRequestResponse`.

### 2.7 `POST /v1/pull-requests/{id}/merge`
Authorizes and executes a governed merge on GitHub.
- **Requirements**:
  - Caller must be an authenticated Human user (`Authorization: Bearer <HUMAN_JWT>`).
  - Governance verdict must be `READY_FOR_MERGE` (or PR status `approved`).
- **Execution**: SUTRA calls the GitHub Merge API using installation credentials.
- **State Transition**: Transitions `PullRequest.status` to `merged`, records `merged_at`, updates originating `Task.status` to `completed`, and records an immutable audit entry.
- **Returns**: `200 OK` with `PRMergeResponse`.

### 2.8 `POST /v1/pull-requests/{id}/close`
Closes the pull request without merging.
- **Returns**: `200 OK` with `PullRequestResponse`.

---

## 3. Governance State Machine

```
   [ Draft / Open ]
          │
          ▼
   (CI Checks Passing)
          │
          ▼
   [ READY_FOR_APPROVAL ]
          │
          ▼
   (Human Approves in SUTRA)
   * Invalidated if HEAD changes!
          │
          ▼
   [ READY_FOR_MERGE ]
          │
          ▼
   (Human Clicks Merge)
          │
          ▼
   [ MERGED ] ──► (Task Completed)
```
