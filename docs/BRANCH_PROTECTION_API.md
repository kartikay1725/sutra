# SUTRA — Branch Protection API Reference (v0.3.3)

This document specifies the REST API endpoints provided by the Branch Protection & Merge Gates system.

---

## Endpoint Summary Matrix

| Method | Endpoint | Description | Authorization |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/repositories/{id}/branch-protection` | Create a branch protection rule | Repository Owner / Admin (`repository.write`) |
| `GET` | `/v1/repositories/{id}/branch-protection` | List all branch protection rules for a repository | Repository Collaborator (`repository.read`) |
| `PATCH` | `/v1/repositories/{id}/branch-protection/{rule_id}` | Update an existing branch protection rule | Repository Owner / Admin (`repository.write`) |
| `DELETE` | `/v1/repositories/{id}/branch-protection/{rule_id}` | Delete a branch protection rule | Repository Owner / Admin (`repository.write`) |

---

## Request & Response Schemas

### BranchProtectionCreateRequest
```json
{
  "branch_pattern": "main",
  "enabled": true,
  "required_approvals": 1,
  "require_change_review": true,
  "require_clean_conflict": true,
  "require_resolved_threads": true,
  "require_agent_review": false,
  "require_no_blocking_agent_findings": false,
  "allow_author_self_approval": false
}
```

### BranchProtectionResponse
```json
{
  "id": "e4f5a6b7-c8d9-0123-ef45-678901234567",
  "repository_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "branch_pattern": "main",
  "enabled": true,
  "required_approvals": 1,
  "require_change_review": true,
  "require_clean_conflict": true,
  "require_resolved_threads": true,
  "require_agent_review": false,
  "require_no_blocking_agent_findings": false,
  "allow_author_self_approval": false,
  "created_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "updated_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "created_at": "2026-08-14T22:38:00Z",
  "updated_at": "2026-08-14T22:38:00Z"
}
```
