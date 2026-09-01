# SUTRA — Pull Request Security Architecture

## 1. Core Security Controls

- **IDOR / BOLA Protections**: Every read and write API operation validates repository access and visibility using SUTRA's centralized `AuthorizationService`. Private repository PRs return `404 Not Found` for unauthorized users.
- **Cross-Repository Invariant Enforcement**: The API layer and database layer enforce that a `Change` cannot be attached to a `PullRequest` belonging to a different repository.
- **Git Argument Injection Protection**: Target branch input is validated using `^[A-Za-z0-9_][A-Za-z0-9._/\-]*$` and explicitly blocks any leading hyphens (`-`) or path traversal sequences (`..`). All subprocess invocations use strict argument arrays (no `shell=True`).
- **UUID & Parameter Sanitization**: Raw database errors are intercepted at the API layer. Malformed UUIDs or invalid formats result in structured HTTP errors (`404` or `422`).
- **Self-Review & Self-Approval Prevention**: Self-approvals by the PR author or underlying Change actor are blocked during state transitions.
- **Audit Metadata Sanitization**: Sensitive keys (`token`, `password`, `jwt`, `secret`, `authorization`) are automatically stripped from JSON audit payloads.
- **Concurrency row locking**: State transitions use PostgreSQL `.with_for_update()` row locking to serialize concurrent requests and prevent double-close/double-approve/double-merge races.
