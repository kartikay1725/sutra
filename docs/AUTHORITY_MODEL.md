# SUTRA V2 Autonomous Engineering Control Plane: Authority Model

## 1. Executive Summary & Substrate Separation

SUTRA is **NOT** a GitHub replacement. It is an **AI-Native Engineering Control Plane** operating directly above the Git and GitHub substrate.

| Substrate (GitHub / Bare Git) | Control Plane (SUTRA) |
|---|---|
| Repositories, Branches, Commits | Agent Task & Session Lifecycle |
| Pull Requests & Discussions | Capability Matching & Dynamic Leasing |
| Issue Tracker & Comments | Code Provenance & SHA-Bound Governance |
| Branch Protection Rulesets | Stale Review Invalidation & Multi-Party Review |
| Code Hosting & Distribution | Pre-receive Policy Hooks & Bypass Detection |

---

## 2. Authority Matrix: Human vs. Agent

Under the SUTRA authority model:
- **Agents NEVER hold unilateral or unrestricted merge authority.**
- **Agents CANNOT review, approve, or sign off on their own Pull Requests.**
- **Human approval is non-negotiable for production merges.**

| Action | Agent (MCP / API) | Human User | Governance Rule |
|---|---|---|---|
| Declare Change / Task | Permitted | Permitted | Change must link to valid Task |
| Push Commit | Governed commits only | Permitted | Verified authorship and pre-receive validation |
| Open Pull Request | Permitted | Permitted | Links Task, Change, and provenance footer |
| Submit Review / Approval | Self-approval prohibited | Permitted | Cross-agent review permitted; self-approval rejected |
| Merge Pull Request | Prohibited without Human Review | Authorized Owners / Reviewers | Evaluates CI PASS + Provenance + SHA-Bound Approval |
| Bypass Git Governance | Rejected at Pre-Receive | Rejected unless admin override | Direct push rejected without valid SUTRA Change key |

---

## 3. SHA-Bound Approvals & Stale Invalidation

To eliminate the risk of race conditions, stealth modifications, or out-of-band force pushes, approvals in SUTRA are strictly **SHA-bound**:

1. **Explicit Binding**: When a reviewer approves a Pull Request via `PullRequestService.review_pull_request`, the approval records `approved_head_sha = pr.head_sha`.
2. **Immediate Invalidation on Update**:
   - On GitHub `pull_request.synchronize` webhook or Git push of new commits, SUTRA resets `approved_head_sha = None`.
   - The Pull Request status reverts from `approved` to `open`.
   - Existing `ChangeReview` records for older commit SHAs are marked `stale`.
   - An audit event `approval.invalidated` is logged to the lifecycle timeline.
3. **GitHub Check Run Synchronization**:
   - SUTRA publishes a mandatory `"SUTRA Governance"` GitHub Check Run.
   - If approvals are invalidated or pending, the check is set to `in_progress` or `failure`.
   - If all governance constraints (CI, provenance, and matching SHA approvals) pass, the check is updated to `success`.

---

## 4. Fork & Open-Source Autonomous Contribution Model

SUTRA natively accommodates open-source and fork workflows where developers and autonomous agents do not have direct write access to upstream repositories:

1. **Connection Types**:
   - `owned`: The user directly owns and controls the repository.
   - `fork`: The repository is a fork connected to an upstream repository.
   - `external_tracked`: Read-only tracking of external repos.
2. **Cross-Repository PR Generation**:
   - Autonomous agents implement changes and push commits to the fork repository.
   - When calling `sutra_open_pull_request` (or `AgentChangeService.create_pull_request`), SUTRA resolves `upstream_repository_id` and automatically directs the PR to the upstream owner with head branch set to `fork_owner:branch`.
3. **Pre-Receive & Cloning**:
   - Any URL or repository can be cloned via `POST /v1/repositories/clone` or the `sutra_clone_repository` MCP tool.
   - Pre-receive hooks and Knowledge Graph indexing are provisioned during cloning.

---

## 5. Curated MCP Interface Boundaries

The SUTRA Model Context Protocol (MCP) server organizes tools into three distinct operational boundaries:

### READ Primitives
- `sutra_get_context`: Authoritative identity, active session, assigned task, and permissions.
- `sutra_search_knowledge`: Knowledge Graph query for symbols, dependencies, and architecture.
- `sutra_get_status`: Full lifecycle status, pipeline stages, blockers, and next legal actions.
- `sutra_get_provenance`: Cryptographic provenance and commit trace chain.
- `sutra_get_governance`: Policy evaluation, branch rules, review status, and merge eligibility.

### WRITE Primitives
- `sutra_start_task`: Claims or initializes an engineering task.
- `sutra_declare_change`: Declares intent and registers a Change record.
- `sutra_push_commit`: Governed commit push with provenance.
- `sutra_open_pull_request`: Opens PR on GitHub/substrate with provenance linking.
- `sutra_submit_change`: Submits change for review/validation.
- `sutra_create_issue`: Files issues/debt reports linked to task context.
- `sutra_create_discussion`: Initiates architectural RFC/discussion on repository.
- `sutra_clone_repository`: Clones external repositories into SUTRA storage.
- `sutra_complete_task`: Finalizes task and records execution/validation summaries.

### PRIVILEGED Primitives
- `sutra_request_merge`: Requests merge under governance policies. Fails if human review or CI criteria are unsatisfied.
