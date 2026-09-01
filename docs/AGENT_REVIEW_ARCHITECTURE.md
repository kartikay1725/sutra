# SUTRA — Agent-Aware Review Platform Architecture (v0.3.2)

## Overview
This document specifies the architectural design for SUTRA's Agent-Aware Review Platform. Agent-Aware Reviews integrate AI and automated agents into the Pull Request and Inline Code Review lifecycle while preserving all existing authoritative boundaries: `Change`, `ChangeReview`, `ChangePolicyService`, `ConflictService`, `AuthorizationService`, and `ChangeEvent`.

---

## Architectural Hierarchy & Component Model

```
Agent Request (Bearer Token Auth)
           │
           ▼
     get_current_agent (app/api/agent_dependencies.py)
           │
           ▼
     AuthorizationService.check(actor, repository, capability)
     ├── Requires actor.type == 'agent'
     ├── Requires actor.owner_id == repository.owner_id
     └── Validates explicit capability (e.g. 'repository.read', 'repository.write')
           │
           ▼
     AgentReviewService (app/services/agent_review_service.py)
     ├── Delegates PR & Change lookup to PullRequestService / ChangeService
     ├── Enforces private repository isolation & cross-repo checks
     ├── Emits structured agent findings & review comments
     └── Transactional audit via ChangeEvent (actor_id = agent.id)
           │
           ├── Agent Inline Comments (InlineReviewComment)
           ├── Agent Findings & Summaries
           └── Human Approval Gate (ChangeReview — Sole Approval Authority)
```

---

## Authoritative Boundaries & Principles

1. **Human vs Agent Authority Boundary**:
   - `ChangeReview` remains the **SOLE** authoritative approval mechanism in SUTRA.
   - Agent reviews, agent comments, agent findings, and agent summaries are strictly **discussion and analysis artifacts**.
   - An agent review or comment **CANNOT** approve a PR, set `ChangeReview` to `approved`, or bypass `ChangePolicyService` or `ConflictService` gates.

2. **Agent Identity & Authentication**:
   - Agents authenticate using SUTRA's existing Bearer token mechanism via `get_current_agent`.
   - Client-supplied `agent_id` or `author_id` claims are never trusted; identity is derived strictly server-side.

3. **Capability & Authorization Boundary**:
   - All agent operations require explicit capability validation via `AuthorizationService.check(actor, repository, capability)`.
   - Agents must own the target repository context (`actor.owner_id == repository.owner_id`).

4. **Persistence & Schema Strategy**:
   - Persistent review feedback, inline comments, and thread replies reuse the existing `InlineReviewComment` table.
   - Transactional audit trails reuse the existing `ChangeEvent` table (`actor_id = agent.id`).
   - Structured findings are represented cleanly without requiring destructive schema modifications.

---

## Audit Event Types (`ChangeEvent`)

- `agent_review.created`
- `agent_review.comment_created`
- `agent_review.reply_created`
- `agent_review.finding_created`
- `agent_review.completed`

Metadata logs include safe identifiers (`pull_request_id`, `repository_id`, `comment_id`, `severity`, `category`, `path`, `line_number`) and exclude secrets, tokens, passwords, and JWTs.

---

## Known Limitations

1. **No Automatic Agent Approvals**: Agents cannot manufacture approvals or satisfy `ChangeReview` approval requirements. Human reviewers remain the sole approval authority.
2. **No Ref Mutations**: Agents cannot directly execute Git ref mutations (`git push`, `git update-ref`, etc.).
