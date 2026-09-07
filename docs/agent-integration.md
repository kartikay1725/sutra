# SUTRA External Agent Integration Guide

> **Version**: 0.4.0 (Private Beta)  
> **Source of Truth**: This document reflects the current SUTRA API implementation and verified control-plane boundaries.

---

## 1. Overview & Fundamental Contract

SUTRA is an AI-Native Engineering Control Plane. External coding agents interact with SUTRA through its REST API and receive scoped Git credentials to push code to the external code substrate (such as GitHub).

**The fundamental contract:**
- An agent performs engineering work under a short-lived, task-bound `AgentSession`.
- SUTRA tracks commit provenance, links the work to a Change and Pull Request, and ingests CI results.
- SUTRA evaluates multi-pillar governance.
- A human reviews and approves the change.
- SUTRA authorizes the governed merge executed on the substrate.
- **Agents cannot self-approve, bypass governance, or merge.**

**API base path**: `/v1/...`  
**OpenAPI docs**: `GET /docs`  
**Agent info**: `GET /v1/agent-info`  
**Protocol handshake**: `POST /v1/agent-protocol/handshake`

---

## 2. Core Engineering Lifecycle

All agents interact with SUTRA along the canonical core engineering lifecycle:

```
Task
 ├──► AgentSession
       ├──► Issue
             ├──► Change
                   ├──► Commit + Provenance
                         ├──► GitHub PR
                               ├──► Checks / CI
                                     ├──► Governance
                                           ├──► Human Approval
                                                 ├──► Governed Merge
                                                       └──► Task Completion
```

---

## 3. Credential Types

There are three primary credential types. Using the wrong credential results in `401 Unauthorized` or `403 Forbidden`.

### A. Human JWT
| Property | Value |
|---|---|
| Format | Opaque string |
| How obtained | `POST /v1/auth/login` |
| Used for | Human-facing API endpoints (`Authorization: Bearer <jwt>`) |
| Expiration | 60 minutes |
| Required for | Agent registration approval, task assignment, review approval, governed merge |

### B. Agent Permanent Token
| Property | Value |
|---|---|
| Format | `sutra_agent_<random>` |
| How obtained | `POST /v1/agents` (human creates) OR registration approval |
| Used for | **Only** `POST /v1/agents/session` to acquire an `AgentSession` |
| NOT accepted by | Standard API endpoints as a session Bearer token |
| Expiration | Never (until revoked by human owner) |

> **Important**: The permanent token is an enrollment credential, not an operational session. Every agent operation requires an active `AgentSession` obtained by exchanging this token.

### C. AgentSession Token
| Property | Value |
|---|---|
| Format | `sutra_session_<random>` |
| How obtained | `POST /v1/agents/session` |
| Used for | Agent API endpoints (`Authorization: Bearer sutra_session_...`) |
| Expiration — absolute | 15 minutes from creation |
| Expiration — idle | 120 seconds without an authenticated request |
| Keepalive | `POST /v1/agents/heartbeat` (send every 30-60s) |

---

## 4. Capability Model

Capabilities are repository-scoped and must be explicitly granted by the repository owner (`POST /v1/repositories/{owner}/{repo}/agents`).

| Capability | Allows | Does NOT Allow |
|---|---|---|
| `repository.read` | Browse code, fetch Git refs, read file trees | Push code |
| `repository.write` | Push commits to feature branches | Merge PRs, push to main |
| `change.create` | Create Change records | Approve changes |
| `change.commit` | Record commit SHA evidence | Bypass review gates |
| `change.conflict.read` | Inspect branch conflict analysis | Force-merge |
| `knowledge_graph.read` | Query semantic entities and relationships | Arbitrary modifications |
| `knowledge_graph.write`| Update semantic entity metadata | Overwrite governance records |

### Authorization Invariants
1. **Explicit grants required**: Once an agent has any `AgentRepositoryAccess` record, access to all repositories requires an explicit enabled grant.
2. **Public visibility bypasses nothing**: Agent capability enforcement applies equally to public and private repositories.
3. **Self-approval prohibited**: An agent cannot approve its own review, approve PRs, or authorize merges.

---

## 5. End-to-End Agent Execution Flow

### Step 1: Human Grants Access
A human owner grants the agent access to the target repository:
```http
POST /v1/repositories/{owner}/{repo}/agents
Authorization: Bearer <HUMAN_JWT>
Content-Type: application/json

{
  "agent_id": "<AGENT_ID>",
  "permissions": ["repository.read", "repository.write", "change.create", "change.commit"],
  "enabled": true
}
```

### Step 2: Agent Creates Session
The agent exchanges its permanent token for an active `AgentSession`:
```http
POST /v1/agents/session
Content-Type: application/json

{
  "token": "sutra_agent_sampletoken123456789"
}
```
Response:
```json
{
  "session_id": "sess_01234567-89ab-cdef-0123-456789abcdef",
  "agent_id": "agnt_01234567-89ab-cdef-0123-456789abcdef",
  "token": "sutra_session_sampletoken987654321",
  "status": "active",
  "expires_at": "2026-09-06T02:00:00Z"
}
```

### Step 3: Agent Claims Task
The agent claims an assigned or open task to acquire an exclusive execution lease:
```http
POST /v1/agent/tasks/{task_id}/claim
Authorization: Bearer <AGENT_SESSION_TOKEN>
```

### Step 4: Agent (Optionally) Creates Substrate Issue
The agent creates a tracked GitHub Issue linked to the task:
```http
POST /v1/agent/tasks/{task_id}/issues
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{
  "title": "Implement feature X specification",
  "body": "Detailed technical implementation notes."
}
```

### Step 5: Agent Pushes Code to Substrate
The agent performs code modifications and pushes a feature branch (`agent/task-xxx`) to the substrate repository.

### Step 6: Agent Creates Change in SUTRA
The agent declares intent in the SUTRA change ledger:
```http
POST /v1/agent/tasks/{task_id}/changes
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{
  "intent": "Implement feature X specification",
  "branch": "agent/feature-x",
  "base_branch": "main",
  "risk_level": "medium"
}
```

### Step 7: Agent Records Commit Evidence
The agent binds the resulting commit SHA to the Change under its active session:
```http
POST /v1/agent/tasks/{task_id}/commit
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{
  "resulting_commit": "a1b2c3d4e5f67890123456789abcdef012345678"
}
```

### Step 8: Agent Creates Pull Request
The agent requests SUTRA to create and link a substrate Pull Request:
```http
POST /v1/agent/tasks/{task_id}/pull-requests
Authorization: Bearer <AGENT_SESSION_TOKEN>
Content-Type: application/json

{
  "title": "feat: implement feature X",
  "target_branch": "main",
  "description": "Automated pull request generated under SUTRA AgentSession."
}
```

### Step 9: Governance & CI Evaluation
GitHub Actions executes CI check runs on the substrate. SUTRA ingests check status via webhooks and computes the 4-pillar governance verdict:
```http
GET /v1/pull-requests/{pr_id}/governance
Authorization: Bearer <HUMAN_JWT>
```

### Step 10: Human Approval
A human reviewer reviews the change diffs and issues approval in SUTRA:
```http
POST /v1/pull-requests/{pr_id}/approve
Authorization: Bearer <HUMAN_JWT>
```
*Note: If the agent pushes another commit, the approval is invalidated automatically.*

### Step 11: Governed Merge
Once governance verdict is `READY_FOR_MERGE`, a human triggers the governed merge:
```http
POST /v1/pull-requests/{pr_id}/merge
Authorization: Bearer <HUMAN_JWT>
```
SUTRA calls the GitHub API to execute the merge, marks the originating Task as `completed`, and records an immutable audit log entry.

---

## 6. What Agents CAN and CANNOT Do

### What an Agent CAN Do:
- Work on its assigned Task.
- Create governed GitHub-backed Issues.
- Create Changes in SUTRA.
- Record commit evidence with cryptographic provenance.
- Create substrate Pull Requests.
- Participate in Discussions where authorized.
- Query the Knowledge Graph and AI Assistant.

### What an Agent CANNOT Do:
- Cannot self-approve its own reviews or pull requests.
- Cannot approve reviews as a human.
- Cannot authorize or execute merges.
- Cannot bypass CI checks or governance verdicts.
- Cannot access private repositories without explicit owner grants.
- Cannot operate outside its assigned task and session lease.

---

## 7. Error Codes

| Status | Meaning | Required Agent Action |
|---|---|---|
| `401 Unauthorized` | AgentSession expired or invalid token | Call `POST /v1/agents/session` to obtain a fresh session. |
| `403 Forbidden` | Missing capability or lease mismatch | Inform human operator to grant required capability. |
| `404 Not Found` | Task or repository ID does not exist | Verify IDs. |
| `409 Conflict` | Task already claimed or commit duplicate | Inspect existing task state. |
| `429 Too Many Requests` | Rate limit reached | Respect `Retry-After` header and back off. |
| `502 Bad Gateway` | Substrate API error | Retry with exponential backoff. |
