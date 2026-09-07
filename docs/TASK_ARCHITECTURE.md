# SUTRA — Task & Agent Execution Architecture

> **Version**: 0.4.0 (Private Beta)  
> **Source of Truth**: Reflects the current SUTRA Control Plane and Task Command Center.

---

## 1. Overview & Architectural Hierarchy

The Task layer is the primary orchestration and command center of SUTRA. Tasks capture high-level engineering objectives and bind them directly to autonomous agents through short-lived, authenticated `AgentSession` leases.

```
Task (WHAT needs to be done)
 ├──► AgentSession (Authoritative execution lease: 15-min TTL)
       ├──► Issue (GitHub-backed decomposition)
             ├──► Change (Authoritative code operation & intent)
                   ├──► Commit + Provenance (Cryptographically bound commit evidence)
                         ├──► GitHub PR (Substrate PR container)
                               ├──► Checks / CI (Automated verification on GitHub)
                                     ├──► Governance (4-pillar policy verdict)
                                           ├──► Human Approval (Reviewer != Requester, HEAD-bound)
                                                 ├──► Governed Merge (SUTRA-authorized substrate merge)
                                                       └──► Task Completion (Terminal state: completed)
```

---

## 2. Core Invariants & Boundaries

1. **Orchestration Layer**: The Task system orchestrates work units and tracks execution progress. It binds an agent to a specific repository and scope.
2. **Lease Model**: An agent claiming a task holds a time-limited lease (`claimed_by_session_id`, `lease_expires_at`). If the session expires or fails to send heartbeats, the lease expires and the task can be reclaimed or reassigned.
3. **Change & Commit Binding**: All changes, commits, and pull requests produced by the agent during execution are explicitly foreign-keyed to the originating Task (`task_id`).
4. **Governed Completion**: Tasks transition to `status="completed"` automatically upon the successful governed merge of their resulting Pull Request.

---

## 3. Data Model Specification (`tasks`)

- `id`: `String(36)` Primary Key (UUIDv4)
- `repository_id`: `String(36)` Foreign Key -> `repositories.id` (ON DELETE CASCADE, Index)
- `created_by`: `String(36)` Foreign Key -> `users.id` (ON DELETE RESTRICT, Index)
- `assigned_agent_id`: `String(36)` Nullable Foreign Key -> `agents.id` (ON DELETE SET NULL, Index)
- `assigned_user_id`: `String(36)` Nullable Foreign Key -> `users.id` (ON DELETE SET NULL, Index)
- `claimed_by_session_id`: `String(36)` Nullable Foreign Key -> `agent_sessions.id` (ON DELETE SET NULL, Index)
- `lease_expires_at`: `DateTime(timezone=True)` Nullable
- `resulting_change_id`: `String(36)` Nullable Foreign Key -> `changes.id` (ON DELETE SET NULL, Index)
- `resulting_pull_request_id`: `String(36)` Nullable Foreign Key -> `pull_requests.id` (ON DELETE SET NULL, Index)
- `title`: `String(255)` Non-null
- `description`: `Text` Nullable
- `status`: `String(30)` Non-null default `'open'` (`open`, `assigned`, `in_progress`, `blocked`, `completed`, `cancelled`)
- `priority`: `String(20)` Non-null default `'medium'` (`low`, `medium`, `high`, `critical`)
- `task_type`: `String(30)` Non-null default `'feature'` (`feature`, `bugfix`, `refactor`, `security`, `documentation`)
- `source`: `String(30)` Non-null default `'user'`
- `created_at`: `DateTime(timezone=True)` Non-null
- `updated_at`: `DateTime(timezone=True)` Non-null
- `started_at`: `DateTime(timezone=True)` Nullable
- `completed_at`: `DateTime(timezone=True)` Nullable
- `cancelled_at`: `DateTime(timezone=True)` Nullable
