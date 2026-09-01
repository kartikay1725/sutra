# SUTRA GitHub Agent Credential Delegation Model

**Phase:** 2 / 3 — Credential Delegation & Identity Architecture  
**Date:** 2026-08-31  
**Status:** Design Document (No code modifications)

---

## 1. Fundamental Identity Invariant

> [!IMPORTANT]
> **SUTRA AgentSession is the SOLE primary agent identity.**
> 
> A GitHub credential is an **ephemeral, downstream provider transport token**. It is never the source of agent identity, never replaces an AgentSession, and carries no authority within SUTRA.

```
┌─────────────────────────────────────────────────────────────┐
│                    SUTRA CONTROL PLANE                      │
│                                                             │
│  [Agent Permanent Token] (sutra_agent_...)                  │
│             ↓                                               │
│  [SUTRA AgentSession]    (sutra_session_...) [15-min TTL]   │
│             ↓                                               │
│  [AuthorizationService]  (repository.read / repository.write│
│             ↓                                               │
│  [CredentialProvider Broker]                                │
└─────────────┬───────────────────────────────────────────────┘
              │ (Brokers short-lived GitHub App Installation Token)
              ↓
┌─────────────────────────────────────────────────────────────┐
│                   EXTERNAL GITHUB SUBSTRATE                 │
│                                                             │
│  [GitHub App Installation Access Token] (ghs_...)           │
│  • Single repository scope                                  │
│  • Exact capability permissions only (contents:read/write)  │
│  • Native GitHub token max lifetime: 1 hour                 │
│  • SUTRA effective maximum TTL: <= 10 minutes               │
│  • SUTRA actively revokes upon session termination          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Answers to Specific Architectural Questions

### Q1: Is SUTRA issuing a GitHub App installation token?
**Yes.** SUTRA acts as a **GitHub App**. When an authenticated agent requests repository Git access, SUTRA uses its GitHub App private key (JWT) to request a scoped **Installation Access Token** (`ghs_...`) from GitHub's `/app/installations/{installation_id}/access_tokens` endpoint on behalf of the agent's authorized task.

---

### Q2: Is the credential ever exposed directly to the agent?
**Yes, in a strictly bounded manner.**
- When the agent performs direct `git clone`, `git fetch`, or `git push` against `github.com`, it requires transport credentials.
- SUTRA provides an authenticated endpoint: `POST /v1/repositories/{owner}/{repo}/token`
- The endpoint requires an active **SUTRA AgentSession Bearer token**.
- SUTRA evaluates `AuthorizationService.check(actor, repo, capability)`. If allowed, SUTRA returns an ephemeral GitHub token (`ghs_...`) along with the exact permitted clone/push URL.
- Alternatively, for agent environments utilizing SUTRA's API-based change submission (non-CLI agents), the agent submits diffs directly to SUTRA, and the agent **never sees any GitHub token at all**.

---

### Q3: What repository scope does it have?
**Strictly Single Repository.**
- Tokens are created using GitHub's `repositories` or `repository_ids` filter in the installation token creation request.
- An installation token issued for repository `org/repo-a` is mathematically rejected by GitHub if used against `org/repo-b`.

---

### Q4: What permission scope does it have?
**Minimal Capability Mapping (No Automatic PR or Merge Rights):**
- If the agent only has `repository.read`:
  `permissions: {"contents": "read", "metadata": "read"}`
- If the agent has `repository.write`:
  `permissions: {"contents": "write", "metadata": "read"}`
  *(Note: `repository.write` does NOT grant `pull_requests:write` or merge capabilities to the agent token).*
- Administrative, repository settings, webhooks, and org management permissions are **never included**.

---

### Q5: What is the maximum TTL?
- **Native vs. Effective TTL:** GitHub App Installation Access Tokens natively have a GitHub-defined fixed expiration of 1 hour.
- **SUTRA Effective Boundary:** SUTRA enforces an **effective maximum lifetime $\le$ 10 minutes** (600 seconds) by recording token leases in Redis, refusing reuse or renewal past 10 minutes, and calling GitHub's `DELETE /installation/token` API endpoint upon SUTRA session expiration or after the 10-minute horizon.

---

### Q6: How does SUTRA prevent capability escalation?
1. **Double Authorization Boundary:**
   Before issuing a downstream GitHub token, SUTRA checks:
   - Is Agent status active in PostgreSQL?
   - Is AgentSession active and unexpired in Redis/PostgreSQL?
   - Does an explicit `AgentRepositoryAccess` record exist for `(agent_id, repository_id)`?
   - Does that record contain the requested capability (`repository.read` or `repository.write`)?
2. **No Wildcard Escalation:** Agents cannot request arbitrary scopes; SUTRA hard-codes the mapping between SUTRA capabilities and GitHub permission parameters.
3. **No Direct Merge Authority:** Installation tokens issued to agents cannot merge PRs or bypass branch rulesets.

---

### Q7: What happens when a SUTRA session expires?
- The agent's SUTRA Bearer token becomes invalid immediately (enforced via Redis + DB checks).
- SUTRA will refuse all subsequent token exchange or refresh requests.
- SUTRA actively calls GitHub's `DELETE /installation/token` API to revoke any downstream tokens linked to that session.

---

### Q8: What happens when SUTRA revokes an agent?
1. Human invokes `POST /v1/agents/{id}/revoke` or repository access revocation.
2. `Agent.is_active` set to `False`; all `AgentSession` records marked `revoked`.
3. SUTRA writes immediate revocation tombstone to Redis (`revoked_session:{id}` and `revoked_agent:{id}`) for 0ms invalidation across all SUTRA API workers.
4. SUTRA executes **active downstream revocation** via `DELETE /installation/token`.

---

### Q9: What happens if a GitHub credential remains valid after SUTRA revocation?
To eliminate the residual window:
1. **Active Invalidation API:** SUTRA tracks issued active GitHub installation tokens in Redis with key `github_tokens:session:{session_id}`.
2. Upon SUTRA session revocation, SUTRA calls GitHub's `DELETE /installation/token` endpoint using the token to revoke it immediately at GitHub's edge.
3. If an unauthorized push still reaches GitHub during a network race, the subsequent GitHub `push` webhook triggers SUTRA's event processor. SUTRA identifies that the push originated from a revoked agent, refuses to correlate it with an authorized Change, marks the branch as untrusted, and fails any PR Check Runs.

---

### Q10: How are Agent, Session, and Change identities correlated?
1. When SUTRA issues a downstream token, it assigns an internal **Credential Issue ID** (`cid-uuid4`) and logs:
   `Correlation = (Agent ID, AgentSession ID, Repository ID, Branch Name, Issued SHA, Timestamp)`
2. Git commits pushed by agents are configured to include a structured trailer:
   `Sutra-Session: <session_id_prefix>` or `Sutra-Agent: <agent_id>`
3. When GitHub emits a `push` or `pull_request` webhook, SUTRA extracts the commit author, ref, and commit SHAs, matching them against active tracked changes for that session.
4. The database links `Change.actor_id = Actor.id (Agent)` and `PullRequest.author_id = Actor.id (Agent)`.

---

### Q11: How is credential leakage handled?
1. **Short Exposure Window:** Bounded effective lifetime ($\le$ 10 min) prevents sustained exploitation.
2. **Audit Logging:** Every token issuance generates an audit log entry in SUTRA with the requesting agent IP, session ID, and timestamp.
3. **Emergency Revocation Endpoint:** `POST /v1/security/revoke-downstream-tokens` instantly revokes all active installation tokens for a repository or organization.
4. **Secret Scanning:** SUTRA inspects incoming webhooks and change diffs for leaked `sutra_session_`, `sutra_agent_`, or `ghs_` patterns, immediately revoking compromised credentials.

---

## 3. Summary of Credential Lifecycle Contract

```
SUTRA Agent Permanent Credential (sutra_agent_...)
    │  (Stored securely by human/agent orchestrator)
    ▼
[Exchanged via POST /v1/agents/session]
    │
    ▼
SUTRA AgentSession Token (sutra_session_...)
    │  • 15-minute rolling TTL
    │  • Validated on every SUTRA API request
    │  • Instant revocation via Redis
    │
    ▼
[POST /v1/repositories/{owner}/{repo}/token]
    │  • Evaluated against AgentRepositoryAccess
    │  • Checks repository.read / repository.write
    │
    ▼
Downstream GitHub Token (ghs_...)
    • Strictly repo-scoped
    • Native GitHub lifetime: 1 hour
    • SUTRA effective lifetime: <= 10 minutes
    • Actively revoked via DELETE /installation/token upon SUTRA session termination
    • Used purely for git transport against github.com
```
