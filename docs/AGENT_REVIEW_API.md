# SUTRA — Agent-Aware Review API Reference (v0.3.2)

This document specifies the REST API endpoints provided by the Agent-Aware Review Platform.

---

## Endpoint Summary Matrix

| Method | Endpoint | Description | Authorization |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/pull-requests/{id}/agent-reviews/comments` | Post an agent review comment or threaded reply | Agent Bearer Token (`repository.write`) |
| `POST` | `/v1/pull-requests/{id}/agent-reviews/findings` | Post a structured agent finding (severity & category) | Agent Bearer Token (`repository.write`) |
| `GET` | `/v1/pull-requests/{id}/agent-reviews` | Get aggregated agent review summary & findings | User / Agent JWT/Bearer (`repository.read`) |

---

## Request & Response Schemas

### AgentCommentCreateRequest
```json
{
  "body": "Agent automated review feedback.",
  "path": "backend/app/main.py",
  "diff_side": "RIGHT",
  "line_number": 42,
  "commit_sha": "1111111111111111111111111111111111111111",
  "parent_id": null
}
```

### AgentFindingCreateRequest
```json
{
  "severity": "high",
  "category": "security",
  "message": "Potential SQL injection vulnerability in dynamic query builder.",
  "path": "backend/app/services/db_service.py",
  "line_number": 88,
  "diff_side": "RIGHT",
  "suggested_fix": "Use parameterized SQLAlchemy query."
}
```

### AgentReviewSummaryResponse
```json
{
  "pull_request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "repository_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "total_findings": 1,
  "severity_distribution": {
    "low": 0,
    "medium": 0,
    "high": 1,
    "critical": 0
  },
  "participating_agents_count": 1,
  "participating_agent_ids": [
    "c3d4e5f6-a7b8-9012-cdef-345678901234"
  ],
  "findings": [
    {
      "pull_request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "repository_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "comment_id": "d4e5f6a7-b890-1234-def5-678901234567",
      "agent_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
      "agent_name": "sec_scanner_agent",
      "severity": "high",
      "category": "security",
      "path": "backend/app/services/db_service.py",
      "line_number": 88,
      "suggested_fix": "Use parameterized SQLAlchemy query."
    }
  ]
}
```
