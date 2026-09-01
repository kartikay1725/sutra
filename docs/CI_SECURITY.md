# SUTRA — CI Security & Execution Isolation Model (v0.3.4)

This document defines the security controls, execution boundaries, and threat mitigations implemented in SUTRA's CI Runner & Automated Verification Platform.

---

## Security Invariants

1. **Secret & Host Environment Stripping**: All host environment variables (`DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, agent tokens, database credentials) are stripped before spawning verification subprocesses.
2. **Process & Shell Safety (`shell=False`)**: Subprocess execution strictly uses explicit argument list vectors (`shell=False`), preventing shell metacharacter injection.
3. **Workspace Isolation & Lifecycle**: Each CI job runs inside an isolated scratch workspace path (`scratch/ci_workspaces/{job_id}`) that is automatically deleted in a `finally` block upon completion.
4. **Log Capping**: Execution stdout/stderr output is truncated at 100 KB to prevent memory exhaustion attacks.
5. **Private Repository Access**: Non-collaborators attempting to access CI endpoints receive HTTP 404 Not Found.
6. **Commit-Specific Gate Invariant**: CI verification is tied to the exact commit SHA of the target `Change`. Pass results for commit A cannot satisfy branch protection requirements for commit B.
