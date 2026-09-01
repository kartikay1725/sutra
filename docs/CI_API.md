# SUTRA — CI Runner & Automated Verification API Reference (v0.3.4)

This document specifies the REST API endpoints provided by SUTRA's CI Runner & Automated Verification Platform.

---

## Endpoint Summary Matrix

| Method | Endpoint | Description | Authorization |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/pull-requests/{pull_request_id}/ci` | Trigger an automated CI verification job | Repository Collaborator (`repository.read` / `write`) |
| `GET` | `/v1/pull-requests/{pull_request_id}/ci` | List all CI verification jobs for a PR | Repository Collaborator (`repository.read`) |
| `GET` | `/v1/pull-requests/{pull_request_id}/ci/{job_id}` | Get status and details of a specific CI job | Repository Collaborator (`repository.read`) |
| `POST` | `/v1/pull-requests/{pull_request_id}/ci/{job_id}/cancel` | Cancel an active or queued CI job | Repository Collaborator (`repository.write`) |
| `GET` | `/v1/pull-requests/{pull_request_id}/ci/{job_id}/logs` | Retrieve execution logs for a CI job | Repository Collaborator (`repository.read`) |

---

## Response Schemas

### CIJobResponse
```json
{
  "id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "pull_request_id": "e4f5a6b7-c8d9-0123-ef45-678901234567",
  "repository_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "change_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "commit_sha": "1111111111111111111111111111111111111111",
  "target_branch": "main",
  "status": "passed",
  "trigger": "pull_request",
  "runner_type": "isolated_process",
  "exit_code": 0,
  "failure_reason": null,
  "worker_id": "api_worker_a1b2c3d4",
  "started_at": "2026-08-14T22:50:00Z",
  "completed_at": "2026-08-14T22:50:02Z",
  "cancelled_at": null,
  "created_at": "2026-08-14T22:50:00Z",
  "updated_at": "2026-08-14T22:50:02Z"
}
```

### CILogResponse
```json
{
  "job_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "status": "passed",
  "output_log": "SUTRA CI Verification Automated Run\nTarget Commit: 1111111111111111111111111111111111111111\n"
}
```
