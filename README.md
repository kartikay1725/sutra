# SUTRA: AI-Native Engineering Control Plane

SUTRA is an AI-Native Engineering Control Plane and Intelligence Layer that orchestrates autonomous coding agents, enforces cryptographic commit provenance, provides deterministic policy and review governance, and controls pull request lifecycles on external code substrates such as GitHub.

---

## 1. Executive Overview & Mission

### Why SUTRA Exists
Traditional developer platforms (like GitHub, GitLab, and Bitbucket) were built around human workflows: humans write code locally, push branches, manually create pull requests, wait for CI checks, request peer reviews, and click merge.

When autonomous AI coding agents (Claude, Codex, Cursor, custom agents) enter engineering workflows, treating them like ordinary human users breaks critical security and governance assumptions:
- Agents can hallucinate or generate malicious commits.
- Long-lived credentials given to agents risk full repository takeover.
- Commits cannot be reliably traced to specific tasks, prompts, or model sessions.
- Agents can attempt to self-review, self-approve, or bypass policies.

**SUTRA solves this by operating as the sovereign Control Plane above the code substrate:**
- SUTRA provides short-lived, lease-based `AgentSession` credentials tied to specific Tasks.
- SUTRA tracks cryptographic commit provenance, verifying whether code was authored by an agent, human, or untracked external actor.
- SUTRA evaluates multi-pillar deterministic policies (CI checks, file conflicts, sensitive file policies, review criteria).
- SUTRA enforces strict human review gates where agent self-approval is cryptographically and logically prohibited.
- SUTRA authorizes and executes governed merges on the external substrate once all safety criteria pass.

---

## 2. Architecture: Control Plane vs. Substrate

```
                       +-------------------------------------------------------+
                       |              SUTRA CONTROL PLANE                      |
                       |                                                       |
                       |  - Human Identity & Sessions (Email + Password / JWT) |
                       |  - Agent Registry, Device Flow & Capabilities         |
                       |  - Short-Lived AgentSession Leases (15-min TTL)       |
                       |  - Task Command Center & Auto-Dispatch                |
                       |  - Changes Ledger & Commit Provenance                 |
                       |  - Multi-Pillar Governance Engine (CI/Risk/Approvals) |
                       |  - Human Review Gate (Self-Approval Prohibited)       |
                       |  - Governed Merge Authorization                       |
                       |  - Semantic Knowledge Graph & AI Assistant            |
                       |  - Real-Time Discussions & Immutable Audit Log        |
                       +---------------------------+---------------------------+
                                                   |
                             authorizes & enforces | delegates token
                                                   v
                       +-------------------------------------------------------+
                       |              GITHUB SUBSTRATE                         |
                       |                                                       |
                       |  - Git Repository & Bare Object Storage               |
                       |  - Pull Request Substrate (Branches & Commits)        |
                       |  - CI / GitHub Actions / Checks Execution             |
                       |  - Substrate Merge Execution                          |
                       +-------------------------------------------------------+
```

### The SUTRA vs. GitHub Boundary

| Surface / Capability | Authoritative Authority | Responsibility |
|---|---|---|
| **Human Authentication** | **SUTRA** | JWT tokens, login, user sessions, organization access. |
| **Agent Identity & Leases** | **SUTRA** | Permanent agent registration, 15-minute `AgentSession` leases, heartbeat, task binding. |
| **Task Management** | **SUTRA** | High-level engineering objectives, priorities, agent auto-dispatch, leases. |
| **Change Ledger & Provenance**| **SUTRA** | Declaration of intent, cryptographic provenance binding (AgentSession + Task + Commit SHA). |
| **Repository Bare Storage** | **GitHub** | Git object database, packfiles, trees, blobs, references, commit DAG. |
| **Pull Request Substrate** | **GitHub** | Head branch, base branch, PR number, diff rendering, commit container. |
| **Pull Request Governance** | **SUTRA** | 4-pillar evaluation (CI, Provenance, Policy, Approvals), verdict computation. |
| **CI Execution** | **GitHub** | GitHub Actions runners, automated test execution, build suites. |
| **CI Verification** | **SUTRA** | Ingests check runs via HMAC-verified webhooks, enforces passing status for mergeability. |
| **Human Review & Approval** | **SUTRA** | Enforces human-only approval, blocks self-review, invalidates approvals on HEAD change. |
| **Merge Authorization** | **SUTRA** | Verifies all gates; authorizes merge only when verdict is `READY_FOR_MERGE`. |
| **Merge Execution** | **GitHub** | Executes the actual Git ref merge or squash via GitHub Merge API. |
| **Knowledge Graph** | **SUTRA** | Semantic code relationships, function calls, class inheritance, task-change links. |
| **AI Assistant** | **SUTRA** | Context-aware engineering assistant linking live control-plane state. |
| **Audit & Activity** | **SUTRA** | Immutable ledger of all sensitive operations, approvals, sessions, and merges. |

---

## 3. Core Engineering Lifecycle

The canonical core engineering lifecycle consists of the following sequential stages, culminating in post-merge task completion:

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

1. **Task**: A high-level engineering work unit is created in SUTRA (e.g., via web UI or API).
2. **AgentSession**: An authorized autonomous agent claims the task and receives a scoped 15-minute `AgentSession` lease.
3. **Issue**: The agent decomposes the task or creates an issue linked to the task.
4. **Change**: The agent declares its engineering intent in the SUTRA change ledger before or during execution.
5. **Commit + Provenance**: The agent pushes code to the substrate branch; SUTRA captures commit evidence and binds agent identity provenance.
6. **GitHub PR**: SUTRA orchestrates a corresponding pull request on GitHub linked to the SUTRA Change and Task.
7. **Checks / CI**: Automated CI workflows run on GitHub (GitHub Actions); SUTRA ingests check runs via secure webhooks.
8. **Governance**: SUTRA evaluates CI status, conflict risk, sensitive file access, and required approvals.
9. **Human Approval**: A human reviewer inspects diffs and issues an approval in SUTRA. If the commit HEAD changes, approval is automatically invalidated. Agents cannot self-approve.
10. **Governed Merge**: SUTRA authorizes and executes the merge on GitHub via the GitHub API, recording an immutable audit entry.
11. **Task Completion**: The post-merge terminal state; SUTRA transitions the task status to completed and archives the session.

---

## 4. User Journey: How SUTRA Is Used

1. **Connect a Repository**: Link your GitHub repository to SUTRA using the GitHub App integration.
2. **Create or Assign a Task**: Create a task from the SUTRA Task Command Center (`/tasks`) and assign an agent.
3. **Agent Receives a Scoped AgentSession**: The agent receives a 15-minute time-to-live lease scoped strictly to the task.
4. **Agent Performs Work**: The agent clones the repository, writes code, commits, and pushes to a feature branch.
5. **SUTRA Records the Change & Provenance**: SUTRA captures the push event, binds the commit SHA to the agent's session, and creates a Change record.
6. **Resulting PR Appears in SUTRA & GitHub**: SUTRA links the pull request, exposing both the SUTRA governance view and a direct link to GitHub.
7. **GitHub Runs CI**: GitHub Actions executes build and test suites on the pushed commits.
8. **SUTRA Evaluates Governance**: SUTRA checks that CI passed, no unauthorized file conflicts exist, and provenance is verified.
9. **Human Reviews and Approves**: A human reviewer reviews the change and approves it in the SUTRA PR detail page.
10. **SUTRA Authorizes Governed Merge**: Once approved and verified, the human clicks "Merge" in SUTRA.
11. **GitHub Executes Merge**: SUTRA calls the GitHub Merge API, updating the base branch.
12. **SUTRA Marks the Task Complete**: The originating task transitions to `completed`, recording the event in the audit log.

### What Users Should Do in GitHub vs. SUTRA

**Use SUTRA for:**
- Task orchestration and agent auto-dispatch.
- Agent session management and capability grants.
- Commit provenance inspection (verifying human vs. agent authorship).
- Multi-pillar governance evaluation and risk verdicts.
- Human review gates and approval enforcement.
- Governed merge authorization.
- Semantic Knowledge Graph exploration.
- Control-plane AI Assistant queries.
- Immutable compliance audit logs.

**Open GitHub for:**
- Full inline PR code discussion threads.
- Comprehensive line-by-line diff and rich file comparisons.
- Deep GitHub Actions runner logs and workflow execution details.
- GitHub-native organization settings and repository permission management.

### What SUTRA Intentionally Does NOT Do

SUTRA does not attempt to clone or replace:
- Git as a distributed version control system.
- GitHub repository bare object storage.
- GitHub Actions CI/CD runner infrastructure.
- GitHub PR comment threads and native markdown reviews.
- Normal substrate manufacturing: **SUTRA does NOT ask users to manually manufacture substrate artifacts** (manual "Create Commit", manual duplicate "Create PR", manual "Create Branch", manual "Run CI").

---

## 5. AgentSession & Capability Model

### AgentSession Architecture

An `AgentSession` is the authoritative execution identity for an agent in SUTRA.

- **Format**: `sutra_session_<random>`
- **Absolute TTL**: 15 minutes
- **Idle TTL**: 120 seconds without an authenticated request
- **Renewal**: Extended via `POST /v1/agents/heartbeat` every 30-60 seconds
- **Binding**: Tied to an Agent and to a Task during execution

**What an AgentSession is NOT:**
- It is NOT a GitHub login or GitHub user account.
- It is NOT a long-lived API key.
- It is NOT permission to approve reviews or authorize merges.

Downstream GitHub installation tokens issued for transport are short-lived substrate credentials and are **not** equivalent to SUTRA `AgentSession` identity.

### Actual Agent Capabilities

| Capability | What an Agent CAN Do | What an Agent CANNOT Do |
|---|---|---|
| `repository.read` | Read files, browse repository code, fetch Git refs. | Push code, modify repository settings. |
| `repository.write` | Push feature branch commits to substrate. | Merge pull requests, push to protected branches. |
| `change.create` | Declare intent and create Change records (`POST /v1/agent/tasks/{id}/changes`). | Finalize without commits, approve changes. |
| `change.commit` | Record commit SHAs under its active session lease. | Self-approve commits, bypass review. |
| `change.conflict.read` | Inspect branch conflict analysis results. | Force-merge conflicting branches. |
| `knowledge_graph.read` | Query semantic entities, functions, and classes. | Modify graph relationships arbitrarily. |
| `knowledge_graph.write`| Update semantic entity metadata from parsed code. | Overwrite control-plane governance data. |

**Forbidden Agent Operations (Enforced at API Level):**
- Agents CANNOT approve their own work.
- Agents CANNOT approve reviews as a human.
- Agents CANNOT authorize or execute merges.
- Agents CANNOT bypass governance policies or CI checks.
- Agents CANNOT impersonate humans or other agents.
- Agents CANNOT access private repositories without explicit grants.
- Agents CANNOT operate outside their assigned Task and Session lease.

---

## 6. Frontend Product Surfaces

All frontend surfaces are built with Next.js and styled for modern engineering workflows:

- **Tasks (`/tasks`, `/tasks/[id]`)**: The primary workflow and control center. Displays task status, priority, assigned agent, execution timeline, real-time terminal output, and direct links to resulting Changes and Pull Requests.
- **Changes (`/changes`, `/changes/[id]`)**: SUTRA-native change and provenance view. Displays commit provenance badges (`SUTRA Agent Provenance`, `Verified Human Commit`, `Substrate Commit`), file diff statistics, and originating task links.
- **Pull Requests (`/pull-requests`, `/pull-requests/[id]`)**: Lightweight substrate view enriched with SUTRA governance context. Features direct `[Open on GitHub]` links, live CI check statuses, governance verdicts, human approval actions, and governed merge execution.
- **CI / Pipelines (`/ci`, `/ci/[id]`)**: Real-time CI jobs and log inspection synchronized from GitHub Actions webhooks.
- **Governance**: Multi-pillar policy verdict display integrated directly into PR and CI detail views (Checks, Provenance, Policy, Reviews).
- **Knowledge Graph (`/knowledge-graph`, `/repositories/[name]/knowledge-graph`)**: Interactive semantic graph mapping files, functions, classes, tasks, and changes.
- **AI Assistant (`/assistant`, `/repositories/[name]/assistant`)**: Repository- and task-aware conversational assistant with live control-plane context.
- **Discussions (`/discussions`, `/repositories/[name]/discussions`)**: Team and agent collaboration channels with governed participation.
- **Audit Log (`/audit-log`)**: Immutable compliance log tracking sensitive actions, approvals, agent sessions, and governance evaluations with CSV export.
- **Activity (`/activity`)**: Human-readable aggregated engineering feed.
- **Repositories (`/repositories`, `/repositories/[name]`)**: Repository browser showing files, commit history, and branches.
- **Agents (`/agents`, `/agents/[id]`)**: Agent registry, token management, and active session monitoring.
- **Settings (`/settings`)**: Account and system configuration.

---

## 7. Authoritative Backend REST APIs

All backend endpoints are served under `/v1` by FastAPI:

### Agent Tasks & Lifecycle
- `POST /v1/agent/tasks/{task_id}/claim`: Claim task and acquire session lease.
- `POST /v1/agent/tasks/{task_id}/heartbeat`: Extend task lease.
- `POST /v1/agent/tasks/{task_id}/release`: Release task lease.
- `POST /v1/agent/tasks/{task_id}/execute`: Mark task in execution.
- `POST /v1/agent/tasks/{task_id}/issues`: Create GitHub-backed issue for task.
- `POST /v1/agent/tasks/{task_id}/changes`: Declare intent and create Change for task.
- `POST /v1/agent/tasks/{task_id}/commit`: Record commit SHA evidence for task.
- `POST /v1/agent/tasks/{task_id}/pull-requests`: Create GitHub PR for task Change.

### Human Tasks
- `GET /v1/tasks`: List all tasks accessible to user.
- `GET /v1/tasks/{task_id}`: Retrieve task details.
- `POST /v1/repositories/{owner}/{repo}/tasks`: Create task.
- `GET /v1/repositories/{owner}/{repo}/tasks`: List repository tasks.
- `POST /v1/tasks/{task_id}/assign`: Assign task to agent or user.
- `POST /v1/tasks/{task_id}/start`: Start task execution.
- `POST /v1/tasks/{task_id}/complete`: Mark task complete.
- `POST /v1/tasks/{task_id}/cancel`: Cancel task.
- `DELETE /v1/tasks/{task_id}`: Delete task (authorized owner only).

### Changes & Commits
- `POST /v1/changes`: Create change (human or agent).
- `GET /v1/changes`: List changes (scoped by repository visibility).
- `GET /v1/changes/{change_id}`: Get change details, diff stats, and linked PR.
- `GET /v1/changes/{change_id}/commits`: List commits with cryptographic provenance.
- `POST /v1/changes/{change_id}/commit`: Record commit evidence.
- `POST /v1/changes/{change_id}/finalize`: Trigger policy evaluation.

### Pull Requests & Governance
- `POST /v1/pull-requests`: Create pull request from change.
- `GET /v1/pull-requests`: List pull requests.
- `GET /v1/pull-requests/{id}`: Get PR details, enriched with checks and governance verdict.
- `GET /v1/pull-requests/{id}/checks`: Get authoritative CI check runs from substrate.
- `GET /v1/pull-requests/{id}/governance`: Evaluate or inspect 4-pillar governance verdict.
- `POST /v1/pull-requests/{id}/approve`: Issue human review approval (self-approval blocked).
- `POST /v1/pull-requests/{id}/merge`: Execute governed merge via GitHub API.
- `POST /v1/pull-requests/{id}/close`: Close pull request.

### Knowledge Graph & Assistant
- `GET /v1/knowledge-graph/{owner}/{repo}/entities`: Retrieve parsed code entities.
- `GET /v1/knowledge-graph/{owner}/{repo}/relations`: Retrieve relationship graph.
- `POST /v1/assistant/threads`: Create conversational assistant thread.
- `POST /v1/assistant/threads/{id}/messages`: Send message and stream AI response.

### Discussions & Collaboration
- `GET /v1/repositories/{owner}/{repo}/discussions`: List repository discussions.
- `POST /v1/repositories/{owner}/{repo}/discussions`: Create architectural RFC or discussion topic.
- `GET /v1/repositories/{owner}/{repo}/discussions/{id}`: Retrieve discussion thread.
- `POST /v1/repositories/{owner}/{repo}/discussions/{id}/comments`: Post comment with human or agent provenance.

### Audit & Activity
- `GET /v1/audit/logs`: Immutable compliance audit log entries.
- `GET /v1/activity`: Aggregated human-readable activity feed.

### Substrate Webhooks
- `POST /v1/webhooks/github`: HMAC-SHA256 authenticated webhook listener for GitHub events (`push`, `pull_request`, `check_run`, `workflow_run`).

### Model Context Protocol (MCP) Agent Primitives
SUTRA exposes high-signal MCP tools for autonomous coding agents (Claude Desktop, Antigravity IDE, Cursor) under `/v1/mcp`:
- **Task & Change Lifecycle**: `sutra_start_task`, `sutra_declare_change`, `sutra_push_commit`, `sutra_open_pull_request`, `sutra_get_status`, `sutra_complete_task`.
- **Governance & Provenance**: `sutra_get_governance`, `sutra_get_provenance`, `sutra_request_merge`.
- **Collaborative Engineering**:
  - `sutra_list_discussions` & `sutra_comment_discussion`: Discover and participate in architecture discussions with verified agent provenance.
  - `sutra_create_discussion`: Propose architectural RFCs and design trade-offs.
  - `sutra_list_issues` & `sutra_create_issue`: Discover backlog work and log technical debt.
  - `sutra_get_ci_logs`: Inspect CI job failures and step execution logs for immediate error diagnosis.
  - `sutra_get_pr_comments` & `sutra_add_pr_comment`: Inspect reviewer feedback threads and reply to code review suggestions.
- **Codebase Intelligence**: `sutra_get_context`, `sutra_search_knowledge`, `sutra_clone_repository`.

---

## 8. Security Guarantees Verified by Audit

1. **Agents Cannot Merge**: The merge endpoint strictly requires an authenticated Human JWT. AgentSession tokens return `403 Forbidden`.
2. **Agents Cannot Self-Approve**: Approvals require Human JWT credentials and enforce `reviewer_id != requester_id`.
3. **HEAD-SHA Approval Invalidation**: Human approvals are cryptographically bound to the reviewed commit HEAD SHA. When new commits are pushed (`pull_request.synchronize`), previous approvals are automatically invalidated.
4. **Private Repository Isolation**: Access to private repository data, changes, tasks, and activity is enforced at database query boundaries; IDOR vulnerabilities are guarded.
5. **HMAC Webhook Verification**: Substrate webhooks require cryptographic HMAC-SHA256 signature verification using `GITHUB_WEBHOOK_SECRET` before processing.
6. **Key Separation**: Webhook secret keys are separated from event integrity hashing keys (`EVENT_INTEGRITY_KEY`).
7. **Sanitized Audit Metadata**: Audit logging redacts sensitive authorization tokens and passwords before writing to the database.
8. **Provenance Integrity**: Commit provenance is tracked via authenticated `AgentSession` leases and push event ingestion, rather than trusting unauthenticated Git author email strings.

---

## 9. Product Status: Beta

SUTRA is currently in **Beta**.

It is actively running live end-to-end engineering lifecycles with GitHub, but has the following known operational limitations:
- **Asynchronous Worker Topology**: Background workers currently run in-process or via lightweight scheduler; a dedicated Celery/Temporal distributed worker tier is recommended for high-volume enterprise deployments.
- **High-Availability Clustering**: Distributed Redis failover and multi-region database replication are not yet configured.
- **Substrate Variety**: GitHub is the primary fully-integrated code substrate. GitLab and Bitbucket adapters are roadmap items.

---

## 10. Environment Configuration

Copy `.env.example` to `.env` and fill in your values. Never commit real secrets.

```bash
# Core Application
APP_NAME=SUTRA
APP_ENV=development
DEBUG=True

# Databases
DATABASE_URL=postgresql://sutra:sutra@localhost:5432/sutra
REDIS_URL=redis://localhost:6379/0

# Security Secrets (Minimum 32 characters each)
JWT_SECRET=your-32-char-min-jwt-secret-key-here
EVENT_INTEGRITY_KEY=your-32-char-min-event-integrity-key-here

# Storage & URLs
REPOSITORY_STORAGE_PATH=./data/repositories
SUTRA_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000

# AI Provider
GROQ_API_KEY=your_groq_api_key_here

# GitHub App Integration
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_github_webhook_secret_here
GITHUB_TEST_REPO_OWNER=sutra-org
GITHUB_TEST_REPO_NAME=sutra-github-e2e-demo
GITHUB_API_BASE_URL=https://api.github.com
```

---

## 11. Developer Quickstart

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Running the Backend
```bash
cd backend
# Create and activate virtual environment
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Unix: source .venv/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running the Frontend
```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000` and communicate with the backend at `http://localhost:8000`.

---

## 12. Testing Commands

All test files listed below exist and have been live-verified against real GitHub repositories:

```bash
# Activate virtual environment
# On Windows: .venv\Scripts\activate
# On Unix: source .venv/bin/activate

# Run individual live lifecycle suites
pytest backend/tests/test_agent_issues_live.py
pytest backend/tests/test_agent_changes_live.py
pytest backend/tests/test_agent_pull_requests_live.py
pytest backend/tests/test_agent_pull_requests_checks_live.py
pytest backend/tests/test_agent_pull_requests_governance_live.py
pytest backend/tests/test_agent_pull_requests_approval_live.py
pytest backend/tests/test_agent_pull_requests_merge_live.py

# Frontend Typecheck and Production Build
cd frontend
npx tsc --noEmit
npm run build
```

---

## License & Ownership

Proprietary — AchintAI. All rights reserved. SUTRA is an AI-Native Engineering Control Plane owned and developed by AchintAI.
