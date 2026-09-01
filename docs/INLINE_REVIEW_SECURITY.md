# SUTRA — Inline Code Review Security Model (v0.3)

This document defines the security controls, validation rules, and vulnerability safeguards implemented in the SUTRA Inline Code Review Platform.

---

## Security Audit Matrix

| Security Threat | Mitigation Control | Verification Result |
| :--- | :--- | :--- |
| **IDOR / BOLA** | Server enforces `AuthorizationService` for all read, write, reply, resolve, and reopen operations against private repositories. | Verified — 404 response on unauthorized private repo access |
| **Path Traversal** | Rejects paths containing `..` or leading hyphens `-`. Validates paths against repository `ChangeFile` records. | Verified — `ValueError("Invalid file path")` |
| **Git Injection** | Diff generation uses argument arrays (`subprocess.run(["git", "--git-dir", ...])`) with no shell interpolation (`shell=False`). | Verified |
| **Author Spoofing** | Author identity (`author_id`) is strictly bound to `current_user.id` authenticated via JWT token. | Verified |
| **Cross-PR Parent Injection** | Validates that `parent_id` comment belongs to the exact same `pull_request_id`. | Verified — `ValueError("Parent comment belongs to a different PullRequest")` |
| **Thread Resolution Race** | Resolving and reopening threads utilizes PostgreSQL `.with_for_update()` row locking. | Verified — Concurrent worker races tested |
| **Audit Metadata Leakage** | All event metadata logs are sanitized to exclude tokens, secrets, JWTs, and passwords. | Verified |
| **Approval Hijacking** | Inline comments cannot modify `ChangeReview` records or bypass policy/conflict gates. | Verified — `ChangeReview` remains sole approval authority |

---

## Architectural Non-Bypass Invariants

1. **ChangeReview Boundary**: Resolving all inline code review comments does **NOT** grant an approval for a `Change` or `PullRequest`. `ChangeReview` remains the sole approval authority.
2. **Private Repository Isolation**: Unauthorized requests to private repository comments or diffs return HTTP 404 to prevent resource enumeration.
