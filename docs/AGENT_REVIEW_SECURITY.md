# SUTRA — Agent-Aware Review Security Model (v0.3.2)

This document defines the security controls, capability validation, and vulnerability safeguards enforced in the SUTRA Agent-Aware Review Platform.

---

## Security Audit Matrix

| Security Threat | Mitigation Control | Verification Status |
| :--- | :--- | :--- |
| **Agent Impersonation** | Agent identity (`agent_id`, `actor_id`) is strictly derived from server-validated Bearer tokens via `get_current_agent`. | Verified — Arbitrary client claims rejected |
| **Capability Bypass** | `AuthorizationService.require(actor, repository, capability)` checks explicit capability list and requires `actor.type == 'agent'`. | Verified |
| **Repository Scope Bypass** | Rejects agent requests if `actor.owner_id != repository.owner_id`. | Verified — PermissionError thrown |
| **Human Approval Hijacking** | Agent reviews and findings do NOT modify `ChangeReview` approval status. | Verified — `ChangeReview` remains sole approval authority |
| **Cross-PR Injection** | Validates that `parent_id` comment belongs to the exact same `pull_request_id`. | Verified |
| **Audit Metadata Leakage** | `ChangeEvent` metadata logs exclude agent tokens, credentials, passwords, secrets, and JWTs. | Verified |
| **Private Repository Enumeration**| Unauthorized requests to private PR agent reviews return HTTP 404. | Verified |

---

## Architectural Non-Bypass Invariants

1. **Human Review Authority**: Agent findings and comments cannot set a Pull Request to `approved` or satisfy `ChangeReview` requirements.
2. **Repository Ownership Boundary**: An agent owned by User B cannot create review comments or findings on a repository owned by User A.
