# SUTRA — Branch Protection Security Model (v0.3.3)

This document defines the security controls, authorization boundaries, and vulnerability mitigations enforced in SUTRA's Branch Protection & Merge Gates layer.

---

## Security Threat Mitigation Matrix

| Security Threat | Mitigation Control | Verification Status |
| :--- | :--- | :--- |
| **IDOR / BOLA Rule Modification** | Rule modification and deletion endpoints verify repository ownership (`repository.owner_id == user.id`) or check `AuthorizationService.check(actor, repo, WRITE)`. | Verified — Cross-owner requests rejected with HTTP 403 |
| **Branch Pattern Injection** | `SAFE_BRANCH_PATTERN` enforces regex `^[a-zA-Z0-9_\-/*.]+$` and explicitly rejects `..` or leading `-` prefixes. | Verified — Injection payloads rejected with HTTP 400 |
| **Self-Approval Bypass** | `allow_author_self_approval=False` explicitly filters out `ChangeReview` records where `reviewer_id == pr.author_id`. | Verified — Self-approvals do not count toward required approvals |
| **ChangePolicy & Conflict Bypass** | Merge gates enforce `ChangePolicyService` ALLOW decision and `ConflictService` LEVEL_NONE requirement. | Verified |
| **Private Rule Leakage** | Repository isolation prevents non-collaborator access to private repository protection rules. | Verified — HTTP 404 returned for unauthenticated/unauthorized access |

---

## Non-Bypass Security Invariants

1. **Policy Ownership**: Branch protection defines branch requirements but delegates policy and review decisions to `ChangePolicyService` and `ChangeReview`.
2. **Deterministic Evaluation**: Evaluation happens atomically inside PostgreSQL transactions with `.with_for_update()` row locking.
