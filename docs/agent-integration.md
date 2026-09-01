# SUTRA External Agent Integration Guide

> **Version**: 0.2.0
> **Source of Truth**: This document reflects the current SUTRA API implementation.
> **Do not invent endpoints, token formats, or capabilities not described here.**

---

## Overview

SUTRA is a Git-compatible engineering platform with a policy-enforced change management system.
External coding agents interact with SUTRA through its HTTP API and Git Smart HTTP transport.

**The fundamental contract:**
- An agent performs engineering work.
- The work is reviewed by a human.
- The human approves or rejects.
- SUTRA enforces this boundary — agents cannot self-approve.

**API base path**: `/v1/...`
**Git base path**: `/git/{owner}/{repo}.git/...`
**OpenAPI docs**: `GET /docs`
**Agent info**: `GET /v1/agent-info`
**Protocol handshake**: `POST /v1/agent-protocol/handshake`

---

## Credential Types

There are four distinct credential types. Using the wrong credential results in 401 or 403.

### A. Human JWT
| Property | Value |
|---|---|
| Format | Opaque string |
| How obtained | `POST /v1/auth/login` |
| Used for | All human API endpoints (`Authorization: Bearer <jwt>`) |
| NOT accepted by | Git HTTP or agent session endpoints |
| Expiration | 60 minutes |

### B. Agent Permanent Token
| Property | Value |
|---|---|
| Format | `sutra_agent_<random>` |
| How obtained | `POST /v1/agents` (human creates) OR registration approval |
| Used for | **Only** `POST /v1/agents/session` to create an AgentSession |
| NOT accepted by | API endpoints as a session Bearer token |
| NOT accepted by | Git HTTP endpoints |
| Expiration | Never (until revoked by owner) |
| Single use? | No — creates new sessions each time |

> **Important**: The permanent token is a credential, not a session. Every agent API call requires
> an active AgentSession obtained by exchanging this permanent token.

### C. AgentSession Token
| Property | Value |
|---|---|
| Format | `sutra_session_<random>` |
| How obtained | `POST /v1/agents/session` |
| Used for | Agent API endpoints AND Git HTTP password |
| Expiration — absolute | 15 minutes from creation |
| Expiration — idle | 120 seconds without any authenticated request |
| Revocation | `POST /v1/agents/session/revoke` |
| On expiry | Create new session with permanent token; retry operation |

> **Critical**: The AgentSession token is the operative credential for all agent work.

### D. Temporary Push Token
| Property | Value |
|---|---|
| Format | `sutra_temp_push_<random>` |
| How obtained | `POST /v1/agents/register` (before approval) |
| Used for | Single-use Git push during pre-approval registration flow only |
| Expiration | 1 hour |
| Single use? | **Yes — consumed on first use. Cannot be reused.** |
| NOT accepted by | Any API endpoint |

---

## Capability Model

### Available Capabilities (Verified)

| Capability | Allows | Does NOT Allow |
|---|---|---|
| `repository.read` | `git clone`, `git fetch`, read API | `git push` |
| `repository.write` | `git push` | Merging, approving reviews |
| `change.create` | `POST /v1/changes/agent` | Approving or finalizing the change |
| `change.commit` | `POST /v1/changes/{id}/agent-commit` | Approving the commit |
| `change.conflict.read` | Read conflict detection API | Resolving conflicts |
| `knowledge_graph.read` | `GET /v1/knowledge-graph` | Modifying the graph |
| `knowledge_graph.write` | Modifying knowledge graph entries | Repository operations |

### Authorization Rules

1. **Explicit grants required**: Once an agent has ANY `AgentRepositoryAccess` record, access to ALL
   repositories (including public ones) requires an explicit enabled grant.
2. **Public visibility bypasses nothing for agents.**
3. **Same-owner bypasses nothing** once any grants exist.
4. **An agent cannot grant itself access** — only the human repository owner can.
5. **Capabilities are repository-scoped** — `repository.write` on repo A does not grant it on repo B.

---

## Step 1 — Human Authentication

```http
POST /v1/auth/register
Content-Type: application/json

{"username": "developer", "email": "dev@example.com", "password": "secure-password"}
```

After email verification:

```http
POST /v1/auth/login
Content-Type: application/json

{"login": "developer", "password": "secure-password"}
```

Response: `{"access_token": "<HUMAN_JWT>", "token_type": "bearer"}`

Use `Authorization: Bearer <HUMAN_JWT>` for all human-facing operations.

---

## Step 2 — Agent Registration

### Path A: Human Creates Agent Directly (Recommended)

```http
POST /v1/agents
Authorization: Bearer <HUMAN_JWT>
Content-Type: application/json

{"name": "my-coding-agent", "description": "Automated coding assistant", "provider": "anthropic", "model": "claude-3-5-sonnet"}
```

Response returns `"token": "sutra_agent_<random>"` **once only** — store it securely.

### Path B: Agent Self-Registration (External Agent Flow)

```http
POST /v1/agents/register
Content-Type: application/json

{
  "agent_name": "external-agent",
  "owner_username": "developer",
  "repo_name": "my-project",
  "new_repo": false,
  "requested_capabilities": ["repository.read","repository.write","change.create","change.commit"]
}
```

Response: `{"id": "<REGISTRATION_ID>", "polling_token": "<POLLING_TOKEN>", "expires_at": "...", "temporary_push_token": "sutra_temp_push_..."}`

Poll for approval:
```http
GET /v1/agents/register/<REGISTRATION_ID>/status?polling_token=<POLLING_TOKEN>
```

- Pending: `{"status": "pending", "permanent_token": null}`
- Approved: `{"status": "approved", "permanent_token": "sutra_agent_<random>"}`

**The human must approve. The agent cannot approve itself.**

Human approves via:
```http
POST /v1/agents/registrations/<REGISTRATION_ID>/approve
Authorization: Bearer <HUMAN_JWT>
```

---

## Step 3 — AgentSession Creation (CRITICAL)

Every agent API call and Git operation requires an active AgentSession.

```http
POST /v1/agents/session
Content-Type: application/json

{"token": "sutra_agent_<random>"}
```

Response:
```json
{
  "session_id": "<SESSION_ID>",
  "agent_id": "<AGENT_ID>",
  "token": "sutra_session_<random>",
  "token_prefix": "sutra_session_xxxx",
  "status": "active",
  "expires_at": "2026-01-01T00:15:00Z",
  "last_seen_at": "2026-01-01T00:00:00Z"
}
```

Use `Authorization: Bearer sutra_session_<random>` for all agent API calls.

| Property | Value |
|---|---|
| Absolute TTL | 15 minutes from creation |
| Idle TTL | 120 seconds without any authenticated request |
| Extension | `POST /v1/agents/heartbeat` every 30-60s |
| On 401 | Create new session with permanent token; retry |

---

## Step 4 — Repository Authorization

**The human repository owner must grant the agent access. The agent cannot do this itself.**

```http
POST /v1/repositories/{owner}/{repo}/agents
Authorization: Bearer <HUMAN_JWT>
Content-Type: application/json

{
  "agent_id": "<AGENT_ID>",
  "permissions": ["repository.read","repository.write","change.create","change.commit"],
  "enabled": true
}
```

**If the agent gets 403 on any repository operation, it MUST inform the human:**
> "I need access to {owner}/{repo}. Please grant me access via
> `POST /v1/repositories/{owner}/{repo}/agents` with agent_id={AGENT_ID}
> and the required permissions."

---

## Step 5 — Git Operations

### Git Authentication Format

```
Username: <token_prefix>       (first 16 chars of permanent agent token: "sutra_agent_AbCd")
Password: <sutra_session_...>  (full AgentSession token)
```

> **Critical**: Git username = permanent token prefix. Git password = AgentSession token.
> Do not swap these.

### Clone and push:

```bash
git clone https://<token_prefix>:<sutra_session_token>@<sutra-host>/git/<owner>/<repo>.git
# make changes
git add . && git commit -m "feat: implement feature X"
git push origin main  # requires repository.write capability
```

| Git Operation | Required Capability |
|---|---|
| `git clone` / `git fetch` | `repository.read` |
| `git push` | `repository.write` |

If the AgentSession expires during a push, the push fails with 401. Create a new session and retry.

---

## Step 6 — Create a Change

After pushing code, declare intent in SUTRA.

**Prerequisites**: Active AgentSession. `change.create` capability on the repository.

```http
POST /v1/changes/agent
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{
  "repository_id": "<REPOSITORY_ID>",
  "intent": "Implement OAuth2 authentication for the login endpoint",
  "base_commit": "abc1234",
  "risk_level": "medium"
}
```

Response: `{"id": "<CHANGE_ID>", "status": "proposed", "resulting_commit": null}`

The Change starts `"proposed"`. It is not approved.

---

## Step 7 — Record Commit Evidence

**Prerequisites**: Active AgentSession. `change.commit` capability. Change in `"proposed"` status.

```http
POST /v1/changes/<CHANGE_ID>/agent-commit
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{"resulting_commit": "def5678"}
```

> **IMPORTANT: This does NOT approve or finalize the Change.**
> Recording a commit establishes evidence. The Change remains `"proposed"`.
> Human review is still required.

---

## Step 8 — Finalize the Change

**Prerequisites**: Active AgentSession. `change.commit` capability. Change must have `resulting_commit`.

```http
POST /v1/changes/<CHANGE_ID>/agent-finalize
Authorization: Bearer <AGENT_SESSION_TOKEN>
```

> **Finalization does NOT bypass human review.**
> If policy requires review, the change awaits human approval regardless of finalization.

---

## Step 9 — Create a Pull Request

**Prerequisites**: Active AgentSession. Change must have `resulting_commit`. Target branch must exist.

```http
POST /v1/pull-requests/agent
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{
  "repository_id": "<REPOSITORY_ID>",
  "source_change_id": "<CHANGE_ID>",
  "title": "feat: implement OAuth2 authentication",
  "description": "Adds OAuth2 support to login endpoint.",
  "target_branch": "main",
  "is_draft": false
}
```

After creating the PR, **inform the human reviewer that the PR is ready for review**.

---

## Step 10 — Human Review

**The agent cannot approve its own PR or review.**

Human requests review:
```http
POST /v1/changes/<CHANGE_ID>/reviews
Authorization: Bearer <HUMAN_JWT>
Content-Type: application/json

{"reason": "Please review the OAuth2 implementation"}
```

A **different** human approves (requester != reviewer is enforced at API level):
```http
POST /v1/changes/<CHANGE_ID>/reviews/<REVIEW_ID>/approve
Authorization: Bearer <DIFFERENT_HUMAN_JWT>
Content-Type: application/json

{"reason": "Implementation correct. Tests pass."}
```

> **Self-review is prohibited**. The human who requested the review cannot approve it.
> Only human users (not agents) can approve via Human JWT.

---

## Step 11 — Merge

**The agent cannot initiate a merge. Merge is a human-only action.**

```http
POST /v1/pull-requests/<PULL_REQUEST_ID>/merge
Authorization: Bearer <HUMAN_JWT>
```

Response: `{"status": "merged", "pull_request_id": "<ID>", "detail": "Pull request merged successfully"}`

---

## Heartbeat and Session Maintenance

Send every 30-60 seconds during active work:

```http
POST /v1/agents/heartbeat
Authorization: Bearer <AGENT_SESSION_TOKEN>
```

---

## Human Permission Boundaries

### Agent MUST ask human when:
- Registration is pending human approval
- 403 on any repository operation (missing access/capability)
- Review is pending human approval
- PR is ready to merge

### Agent MUST NOT:
- Grant itself repository access
- Approve its own review or PR
- Merge without human authorization
- Reuse expired or revoked tokens
- Use another user's credentials
- Escalate capabilities beyond what is granted

---

## Failure Handling

| Status | Meaning | Action |
|---|---|---|
| `401` | Invalid/expired session | Create new AgentSession; retry |
| `403` | Missing capability or access | Inform human; ask them to grant access |
| `404` | Resource not found | Verify IDs |
| `409` | Conflict (duplicate, policy block) | Check state; resolve before retrying |
| `429` | Rate limited | Respect `Retry-After`; back off |
| `503` | Security service unavailable | Back off exponentially; do not retry immediately |

