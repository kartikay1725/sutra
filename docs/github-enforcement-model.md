# SUTRA vs. GitHub Enforcement Model

**Phase:** 2 / 3 — Enforcement & Gate Analysis  
**Date:** 2026-08-31  
**Status:** Design Document (No code modifications)

---

## 1. Overview & Core Principle

In SUTRA, **SUTRA is the policy and governance authority**. GitHub is the external engineering substrate (hosting Git objects, PRs, branch references, and merge mechanics).

> [!IMPORTANT]
> **A GitHub Check Run is NOT a push-time Git pre-receive equivalent.**
> - A **Git pre-receive hook** executes synchronously on the Git server during `git push` *before* any ref update is accepted. It can reject bytes at transport time.
> - A **GitHub Check Run** is an asynchronous status signal reported to GitHub by an App. It communicates SUTRA’s evaluation to humans and branch protection rules.
> - **Feature branch pushes reach GitHub before SUTRA evaluation.** SUTRA observes the push via webhook, creates a pending/blocked Check Run, and **prevents the resulting Change from becoming mergeable** until all policy, review, and human approval gates pass.
> - **GitHub Branch Protection / Rulesets** constitute the actual repository-side enforcement boundary against merging or direct branch manipulation on protected branches.

---

## 2. Pre-Receive Hook Behavior Today (Local SUTRA)

In SUTRA v0.3.x (local bare Git hosting):

```
Agent Git Push (git-receive-pack)
       ↓
SUTRA Git HTTP Proxy (git_http.py)
   [Basic Auth: Session Token]
       ↓
Local Bare Repository
       ↓
hooks/pre-receive (git_pre_receive.py)
   [Synchronous Python Subprocess]
       ↓
1. Checks SUTRA Actor & Agent active status in DB
2. Checks AgentRepositoryAccess (repository.write)
3. Evaluates RefUpdateProposal (blocks force push, blocks branch delete)
       ↓
   Decision:
   ├─ ALLOW  → Git accepts ref update & writes commit
   └─ BLOCK  → Git rejects packfile instantly; ref NOT updated
```

### Properties of Current Local Pre-Receive Hook:
1. **Synchronous rejection:** Unauthorized pushes fail during the network transfer of `git push`.
2. **Zero repository pollution:** Rejected commits are never referenced by any branch ref.
3. **Tight coupling:** Requires local execution rights and file system hooks on the Git host.

---

## 3. GitHub Behavior After Migration

GitHub does not allow 3rd-party SaaS or GitHub Apps to run arbitrary server-side pre-receive scripts on `github.com` (custom pre-receive hooks are restricted to GitHub Enterprise Server on-premise).

Therefore, SUTRA enforces security across two distinct phases:

```
[ PHASE 1: PUSH / TRANSPORT TIME ]
Agent requests push capability from SUTRA
       ↓
SUTRA checks: Active AgentSession + repository.write capability grant
       ↓
SUTRA issues short-lived, repo-scoped GitHub Installation Token (Effective TTL <= 10 min)
       ↓
Agent pushes branch directly to GitHub (e.g., refs/heads/agent/feature-1)
       ↓
GitHub receives push → Fires `push` Webhook to SUTRA
       ↓
SUTRA processes push, validates commit SHAs, records GitPushEvent + Change evidence


[ PHASE 2: PULL REQUEST & MERGE GATE ]
Agent creates PR (mirrored to GitHub PR)
       ↓
SUTRA evaluates ChangePolicyService + BranchProtectionService
       ↓
SUTRA GitHub App creates/updates Check Run on GitHub PR:
   ├─ If Policy ALLOW  → Check Run Status: SUCCESS (Neutral / Passed)
   └─ If Policy BLOCK  → Check Run Status: FAILURE / ACTION_REQUIRED
       ↓
GitHub Branch Ruleset blocks merge if SUTRA Check Run is not SUCCESS
       ↓
Merge only executes when Human explicitly approves in SUTRA (Requester ≠ Reviewer)
       ↓
SUTRA triggers GitHub Merge API using SUTRA App authority
```

---

## 4. Comprehensive Enforcement Matrix

| Lifecycle Action | Local SUTRA Mechanism | GitHub Substrate Equivalent | Enforcement Timing | Can Unauthorized Action Bypass SUTRA? |
|------------------|-----------------------|-----------------------------|--------------------|---------------------------------------|
| **Clone / Fetch** | SUTRA Git HTTP proxy (Basic Auth) | Scoped GitHub Installation Token issued by SUTRA | Token Issuance Time | **No.** SUTRA must grant token first; effective token lifespan $\le$ 10 min. |
| **Direct Push to Protected Branch (`main`)** | Pre-receive hook rejects push | GitHub Ruleset: "Restrict pushes / Require PR" | Push Time (GitHub-enforced) | **No.** GitHub rejects direct push to protected branch. |
| **Push to Agent Feature Branch** | Pre-receive hook verifies `repository.write` | SUTRA issues push token only if agent has `repository.write` | Token Issuance Time + Webhook observation | **No.** Agent without grant cannot acquire GitHub push token. If an unpermitted push occurs, SUTRA blocks PR mergeability. |
| **Force Push (`--force`)** | Pre-receive hook rejects non-fast-forward | GitHub Ruleset: "Block force pushes" | Push Time (GitHub-enforced) | **No.** GitHub rejects force push on rule-matched branches. |
| **Branch Deletion** | Pre-receive hook rejects delete ref | GitHub Ruleset: "Block branch deletions" | Push Time (GitHub-enforced) | **No.** GitHub blocks deletion. |
| **Merging without Review / Policy** | Local `pull_request_service.py` checks approval before CAS merge | GitHub Ruleset: "Require status check to pass (SUTRA Policy Engine)" + "Require SUTRA Human Approval" | Merge Time (GitHub & SUTRA-enforced) | **No.** GitHub blocks merge until SUTRA Check Run passes; SUTRA alone holds merge API authority. |
| **Agent Self-Approval** | SUTRA DB invariant: `requester_id != reviewer_id` | SUTRA ChangeReview API rejects agent identity | API Request Time | **No.** Handled entirely inside SUTRA control plane. |

---

## 5. What is Enforceable vs. Observable

### What is Enforceable Before Merge (Hard Gates):
1. **Merge Gate:** Unauthorized or unreviewed code cannot enter `main` / production branches because GitHub rulesets enforce the SUTRA Check Run requirement.
2. **Credential Gate:** Unregistered or un-permitted agents cannot push or clone because SUTRA will not issue downstream GitHub installation tokens.
3. **Protected Branch Protection:** Direct pushes to protected branches are rejected by GitHub rulesets at push time.
4. **Human Approval Gate:** SUTRA API strictly enforces human JWT authentication and distinct reviewer identity (`requested_by != reviewer_id`).

### What is Observable After Push (Audit & Evidence):
1. **Feature branch pushes:** When an agent pushes a feature branch (`agent/task-42`), the commits arrive at GitHub *prior* to SUTRA payload evaluation. SUTRA receives the `push` webhook, computes commit/file deltas, and records cryptographic push events.
2. **Uncoordinated pushes:** If a token is misused to create arbitrary feature branches, SUTRA observes the webhook, marks the activity as untracked/suspicious, and sets any PR Check Run to `FAILURE`, preventing merge.

### What Cannot Be Enforced at Wire Time by GitHub (Differences from Pre-Receive):
1. **Feature branch transport filtering:** If an agent possesses a valid GitHub token scoped to a repo, GitHub will accept a push to a non-protected branch (`agent/*`) without invoking SUTRA synchronously during the TCP/SSH/HTTP stream. SUTRA evaluates the content immediately upon webhook arrival and blocks mergeability.

---

## 6. Residual Security Risks & Mitigations

```
┌──────────────────────────────────────────────┬────────────────────────────────────────────────────────┐
│ Residual Risk                                │ Mitigation Strategy                                    │
├──────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ 1. Malicious branch clutter                  │ - GitHub token scoped with effective TTL <= 10 mins.   │
│    (Agent pushes 100 junk feature branches)  │ - Ephemeral branch naming pattern (`sutra/agent-...`). │
│                                              │ - Auto-pruning worker for stale/unlinked agent refs.   │
├──────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ 2. Bypass via direct GitHub Web UI merge     │ - Repository branch rulesets require SUTRA Check Run.  │
│                                              │ - Restrict merge rights strictly to SUTRA GitHub App.  │
│                                              │ - Humans interact through SUTRA control plane.         │
├──────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ 3. Stale GitHub credential after SUTRA       │ - SUTRA enforces effective TTL <= 10 min in Redis.     │
│    session revocation                        │ - Immediate GitHub installation token revocation API   │
│                                              │   (`DELETE /installation/token`) on SUTRA revocation.  │
│                                              │ - Immediate Redis-backed session invalidation.         │
├──────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ 4. Webhook delivery delay or loss            │ - Out-of-band reconciliation poller (every 30s).       │
│                                              │ - HMAC-SHA256 signature verification on all webhooks.  │
│                                              │ - Check Run state defaults to `PENDING` (fail-closed). │
└──────────────────────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 7. Summary of Architectural Contract

1. SUTRA never relinquishes policy authority to GitHub.
2. SUTRA expresses its policy to GitHub via **Check Runs** and **Repository Rulesets**.
3. SUTRA maintains authoritative state machine status in PostgreSQL (`changes`, `pull_requests`, `change_reviews`).
4. GitHub enforces the physical barrier to branch merges based on SUTRA Check Runs.
