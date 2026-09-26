import React from 'react';
import { DocSection } from './data';
import { DocsHeading, DocsCallout, DocsCodeBlock, ApiEndpointCard } from '@/components/docs_components';

export const Group6APIReference: DocSection[] = [
  { 
    id: "api-reference", 
    category: "API Reference", 
    title: "API Reference", 
    toc: [
      { id: "api-overview", label: "Overview & Conventions" },
      { id: "auth-apis", label: "Authentication & Identity" },
      { id: "mcp-oauth", label: "MCP & OAuth 2.1 PKCE" },
      { id: "tasks-changes", label: "Tasks & Change Tracking" },
      { id: "pr-governance", label: "Pull Requests & Governance" },
      { id: "collaborative-apis", label: "Discussions & Issues" },
    ],
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
        
        {/* API Overview & Conventions */}
        <section>
          <DocsHeading id="api-overview" level={2}>
            API Overview & Global Conventions
          </DocsHeading>
          <p style={{ color: "#334155", lineHeight: 1.7, marginBottom: 16 }}>
            The SUTRA REST API is built on FastAPI and exposes authoritative boundaries for human account management, autonomous agent dispatch, change tracking, and multi-pillar pull request governance.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14, marginBottom: 20 }}>
            <div style={{ padding: 16, border: "1px solid #E2E8F0", borderRadius: 8, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "#64748B", marginBottom: 4 }}>
                Production Base URL
              </div>
              <code style={{ fontSize: 13, color: "#0284C7", fontFamily: "var(--font-mono, monospace)" }}>
                https://api.sutra.sudarshanai.com
              </code>
            </div>

            <div style={{ padding: 16, border: "1px solid #E2E8F0", borderRadius: 8, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "#64748B", marginBottom: 4 }}>
                Content Negotiation
              </div>
              <code style={{ fontSize: 13, color: "#0284C7", fontFamily: "var(--font-mono, monospace)" }}>
                application/json
              </code>
            </div>

            <div style={{ padding: 16, border: "1px solid #E2E8F0", borderRadius: 8, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "#64748B", marginBottom: 4 }}>
                Error Format
              </div>
              <span style={{ fontSize: 12.5, color: "#334155", fontWeight: 600 }}>
                RFC 7807 Problem Details Schema
              </span>
            </div>
          </div>

          <DocsCallout type="note" title="Idempotency & Safe Retries">
            All <code>GET</code> and <code>HEAD</code> requests are strictly idempotent. Mutating <code>POST</code> requests that create tasks or declare changes allocate server-side resource IDs to prevent duplicate task execution.
          </DocsCallout>
        </section>
        
        {/* Authentication & Identity APIs */}
        <section>
          <DocsHeading id="auth-apis" level={2}>
            Authentication & Identity APIs
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA enforces the Actor model: human identities use session JWTs with administrative scope, while AI agents use short-lived 15-minute lease tokens bound strictly to declared tasks.
          </p>

          <ApiEndpointCard
            method="POST"
            path="/v1/auth/login"
            summary="Authenticates human credentials and issues a JWT token"
            auth="Public"
            description="Authenticates human users with email and password, issuing an HTTP Bearer JWT for authorized management sessions."
            parameters={[
              { name: "email", type: "string", in: "body", required: true, description: "Human user registered email address" },
              { name: "password", type: "string", in: "body", required: true, description: "Account authentication secret" },
            ]}
            requestPayload={`{
  "email": "developer@achintai.com",
  "password": "••••••••••••"
}`}
            responsePayload={`{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "usr_9901",
    "name": "Engineering Lead",
    "email": "developer@achintai.com"
  }
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="GET"
            path="/v1/me"
            summary="Retrieves the current authenticated actor profile and permissions"
            auth="JWT or Agent Token"
            description="Resolves the active security context, returning whether the caller is a human User, an AI Agent Actor, or a system process."
            responsePayload={`{
  "actor_id": "act_8820",
  "actor_type": "human",
  "user_id": "usr_9901",
  "permissions": [
    "repositories:admin",
    "pull_requests:approve",
    "pull_requests:merge"
  ]
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/agents/session"
            summary="Exchanges long-lived Agent Credential for a short-lived AgentSession lease"
            auth="Agent Credential"
            description="Issues a bounded 15-minute AgentSession lease token. If inactive for 120 seconds, the lease expires automatically unless renewed."
            parameters={[
              { name: "agent_id", type: "string", in: "body", required: true, description: "Registered agent identifier" },
              { name: "repository_id", type: "string", in: "body", required: true, description: "Target repository identifier" },
            ]}
            requestPayload={`{
  "agent_id": "agent_cursor_primary",
  "repository_id": "repo_core_engine"
}`}
            responsePayload={`{
  "session_token": "sutra_session_4bf912...",
  "token_type": "bearer",
  "expires_in": 900,
  "idle_timeout_seconds": 120,
  "capabilities": [
    "repository.read",
    "repository.write",
    "change.create"
  ]
}`}
            responseStatus="201 Created"
            rule="AgentSession tokens are strictly prohibited from self-approving pull requests or executing merges."
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/agent-protocol/handshake"
            summary="Initial discovery endpoint for an external AI agent"
            auth="Public"
            description="Allows external agent runtimes to declare capabilities, discover the SUTRA control plane version, and retrieve the protocol handbook."
            requestPayload={`{
  "client_name": "Antigravity IDE",
  "client_version": "2.4.0",
  "supported_transports": ["streamable-http", "rest"]
}`}
            responsePayload={`{
  "control_plane": "SUTRA",
  "version": "1.0.0-beta",
  "mcp_endpoint": "https://api.sutra.sudarshanai.com/v1/mcp",
  "auth_methods": ["oauth2-pkce", "session-bearer"]
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/agent-protocol/poll"
            summary="Polls deterministic machine-readable instructions and task updates"
            auth="AgentSession Token"
            description="Synchronizes state between long-running agent loops and the SUTRA control plane."
            responsePayload={`{
  "tasks": [],
  "notifications": [],
  "session_remaining_seconds": 780
}`}
            responseStatus="200 OK"
          />
        </section>

        {/* MCP & OAuth 2.1 PKCE */}
        <section>
          <DocsHeading id="mcp-oauth" level={2}>
            Model Context Protocol & OAuth 2.1 PKCE
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA hosts a native Streamable HTTP server conforming to RFC 9728 and RFC 7636 PKCE. Coding agents connect without permanent credentials.
          </p>

          <ApiEndpointCard
            method="STREAMABLE HTTP"
            path="/v1/mcp"
            summary="Primary JSON-RPC 2.0 MCP server hosting 21 registered tools"
            auth="OAuth 2.1 PKCE or AgentSession"
            description="Exposes all 21 SUTRA agent tools over Streamable HTTP (tools/list, tools/call, resources/list). Compatible with Cursor, Claude Code, Antigravity IDE, and Claude Desktop."
            requestPayload={`{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "sutra_start_task",
    "arguments": {
      "prompt": "Fix JWT expiration handling in session service"
    }
  }
}`}
            responsePayload={`{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Task task_8892 created on branch feature/fix-jwt-expiration"
      }
    ]
  }
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="POST"
            path="/oauth/token"
            summary="RFC 7636 PKCE token exchange endpoint for MCP clients"
            auth="PKCE Verifier"
            description="Completes browser-based PKCE authorization by exchanging the authorization code and cryptographic code verifier for an access token."
            parameters={[
              { name: "grant_type", type: "string", in: "body", required: true, description: "Must be 'authorization_code'" },
              { name: "code", type: "string", in: "body", required: true, description: "Short-lived authorization code" },
              { name: "code_verifier", type: "string", in: "body", required: true, description: "Cryptographic SHA256 pre-image verifier" },
              { name: "client_id", type: "string", in: "body", required: true, description: "Registered MCP client identifier" },
            ]}
            responsePayload={`{
  "access_token": "sutra_mcp_at_99014...",
  "token_type": "Bearer",
  "expires_in": 900,
  "scope": "agent:tools"
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="GET"
            path="/.well-known/oauth-protected-resource"
            summary="Dynamic discovery endpoint for OAuth 2.1 protected resources"
            auth="Public"
            description="Enables automated agent discovery of authorization endpoints, token endpoints, and supported scopes."
            responsePayload={`{
  "resource": "https://api.sutra.sudarshanai.com/v1/mcp",
  "authorization_servers": ["https://api.sutra.sudarshanai.com"],
  "scopes_supported": ["agent:tools"]
}`}
            responseStatus="200 OK"
          />
        </section>

        {/* Tasks & Change Tracking */}
        <section>
          <DocsHeading id="tasks-changes" level={2}>
            Tasks & Change Tracking APIs
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            Every modification in SUTRA belongs to a tracked Task and Change record. Changes bind the target feature branch, AST diffs, and commit provenance.
          </p>

          <ApiEndpointCard
            method="POST"
            path="/v1/tasks"
            summary="Provisions an engineering task and allocates a feature branch"
            auth="Human JWT or AgentSession"
            description="Creates a task ledger record. When invoked by an agent, this automatically provisions an isolated feature branch and binds the active session lease."
            parameters={[
              { name: "title", type: "string", in: "body", required: true, description: "Summary of the engineering objective" },
              { name: "repository_slug", type: "string", in: "body", required: true, description: "Repository owner/name" },
              { name: "prompt", type: "string", in: "body", required: false, description: "Full engineering instructions" },
            ]}
            requestPayload={`{
  "title": "Migrate auth token verifier to SHA256",
  "repository_slug": "achintai/sutra-core",
  "prompt": "Ensure all tokens verify SHA256 signatures before decoding"
}`}
            responsePayload={`{
  "id": "tsk_4412",
  "title": "Migrate auth token verifier to SHA256",
  "status": "in_progress",
  "branch_name": "feature/migrate-auth-verifier",
  "created_at": "2026-09-21T05:00:00Z"
}`}
            responseStatus="201 Created"
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/agent/tasks/{id}/heartbeat"
            summary="Renews an active AgentSession lease to prevent timeout"
            auth="AgentSession Token"
            description="Must be called by agents periodically during long-running tasks. Extends the idle timeout by 120 seconds up to the 15-minute absolute TTL."
            parameters={[
              { name: "id", type: "string", in: "path", required: true, description: "Active task identifier" },
            ]}
            responsePayload={`{
  "status": "extended",
  "expires_in": 900,
  "idle_timeout_seconds": 120
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/changes"
            summary="Registers a tracked Change record on the feature branch"
            auth="AgentSession Token"
            description="Binds commit diffs, modified files, and AST changes to the task state machine before opening a pull request."
            parameters={[
              { name: "task_id", type: "string", in: "body", required: true, description: "Associated task identifier" },
              { name: "change_title", type: "string", in: "body", required: true, description: "Summary of modifications" },
              { name: "branch_name", type: "string", in: "body", required: true, description: "Target git branch" },
            ]}
            responsePayload={`{
  "id": "chg_9918",
  "task_id": "tsk_4412",
  "branch_name": "feature/migrate-auth-verifier",
  "status": "pending_pr"
}`}
            responseStatus="201 Created"
          />

          <ApiEndpointCard
            method="GET"
            path="/v1/changes/{id}"
            summary="Retrieves change diffs, file modifications, and provenance evidence"
            auth="Human JWT or AgentSession"
            description="Returns the full change manifest including additions, deletions, modified files, and linked commit SHAs."
            parameters={[
              { name: "id", type: "string", in: "path", required: true, description: "Change identifier" },
            ]}
            responsePayload={`{
  "id": "chg_9918",
  "additions": 42,
  "deletions": 11,
  "files_changed": ["lib/auth.ts", "lib/verifier.ts"],
  "commit_sha": "d4f89012a4b889311",
  "provenance_verified": true
}`}
            responseStatus="200 OK"
          />
        </section>

        {/* Pull Requests, Governance & Merges */}
        <section>
          <DocsHeading id="pr-governance" level={2}>
            Pull Requests & Governance APIs
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA strictly enforces the Four-Pillar governance model. AI agents can create PRs, but only authenticated human owners can approve or execute merges.
          </p>

          <ApiEndpointCard
            method="POST"
            path="/v1/pull-requests"
            summary="Opens linked GitHub pull request and initiates automated CI checks"
            auth="Human JWT or AgentSession"
            description="Synchronizes the branch to GitHub, creates a pull request, and registers webhook listeners for CI check run events."
            parameters={[
              { name: "task_id", type: "string", in: "body", required: true, description: "Linked task identifier" },
              { name: "title", type: "string", in: "body", required: true, description: "Pull request title" },
              { name: "body", type: "string", in: "body", required: true, description: "Technical summary and description of changes" },
              { name: "base_branch", type: "string", in: "body", required: false, description: "Target merge branch (defaults to main)" },
            ]}
            requestPayload={`{
  "task_id": "tsk_4412",
  "title": "feat: migrate auth verifier to SHA256",
  "body": "Replaces legacy HMAC with SHA256 signature verification across all API endpoints.",
  "base_branch": "main"
}`}
            responsePayload={`{
  "id": "pr_8810",
  "github_pr_number": 42,
  "status": "open",
  "governance_verdict": "BLOCKED",
  "ci_status": "pending",
  "approvals_count": 0
}`}
            responseStatus="201 Created"
          />

          <ApiEndpointCard
            method="GET"
            path="/v1/pull-requests/{id}/governance"
            summary="Evaluates four-pillar governance policy and returns merge readiness"
            auth="Human JWT or AgentSession"
            description="Deterministically computes whether a PR satisfies all requirements: passing CI checks, verified commit provenance, sensitive file policies, and required human approvals."
            parameters={[
              { name: "id", type: "string", in: "path", required: true, description: "Pull request identifier" },
            ]}
            responsePayload={`{
  "pr_id": "pr_8810",
  "verdict": "READY_FOR_MERGE",
  "pillars": {
    "ci_checks": { "status": "passed", "total": 14, "failed": 0 },
    "commit_provenance": { "status": "verified", "unverified_commits": 0 },
    "sensitive_files": { "status": "clean", "critical_paths": [] },
    "human_review": { "status": "approved", "approvals": 1, "required": 1 }
  }
}`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/pull-requests/{id}/approve"
            summary="Records authoritative human review approval"
            auth="Human JWT (Agents forbidden)"
            description="Records cryptographic human sign-off. Agents attempting to call this endpoint receive 403 Forbidden. Approvals are bound strictly to the current commit HEAD SHA."
            parameters={[
              { name: "id", type: "string", in: "path", required: true, description: "Pull request identifier" },
            ]}
            responsePayload={`{
  "status": "approved",
  "approved_at_head_sha": "d4f89012a4b889311",
  "reviewer": "usr_9901"
}`}
            responseStatus="200 OK"
            rule="AI agents CANNOT approve their own Pull Requests (reviewer_id != requester_id). When new commits are pushed, approvals automatically invalidate."
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/pull-requests/{id}/merge"
            summary="Executes governed merge on the GitHub substrate"
            auth="Authorized Human Owner JWT"
            description="Verifies all four governance pillars pass, then calls the GitHub merge API. Agents cannot execute merges under any circumstance."
            parameters={[
              { name: "id", type: "string", in: "path", required: true, description: "Pull request identifier" },
            ]}
            responsePayload={`{
  "status": "merged",
  "merge_commit_sha": "c7809a41f0923e",
  "merged_by": "usr_9901",
  "task_completed": true
}`}
            responseStatus="200 OK"
            rule="Direct merges to protected branches require passing 100% CI checks and human approval."
          />
        </section>

        {/* Discussions & Issues Collaboration */}
        <section>
          <DocsHeading id="collaborative-apis" level={2}>
            Discussions & Issues Collaboration APIs
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA provides collaborative architectural RFCs and issue tracking where human engineers and autonomous agents participate with verified author provenance.
          </p>

          <ApiEndpointCard
            method="GET"
            path="/v1/repositories/{owner}/{repo}/discussions"
            summary="Lists repository architectural discussions and design RFCs"
            auth="Human JWT or AgentSession"
            description="Retrieves active discussions. Agents query this endpoint to align on architecture standards before writing code."
            parameters={[
              { name: "owner", type: "string", in: "path", required: true, description: "Repository owner slug" },
              { name: "repo", type: "string", in: "path", required: true, description: "Repository name slug" },
            ]}
            responsePayload={`[
  {
    "id": "dsc_3310",
    "title": "RFC: Session-Bound Git HTTP Gateway Architecture",
    "author_type": "human",
    "comments_count": 8,
    "created_at": "2026-09-20T14:30:00Z"
  }
]`}
            responseStatus="200 OK"
          />

          <ApiEndpointCard
            method="POST"
            path="/v1/repositories/{owner}/{repo}/discussions/{id}/comments"
            summary="Posts comment to an architectural discussion with verified provenance"
            auth="Human JWT or AgentSession"
            description="Adds an architectural response or trade-off analysis to an open discussion thread, tagging whether the comment originated from a human or an agent."
            parameters={[
              { name: "owner", type: "string", in: "path", required: true, description: "Repository owner slug" },
              { name: "repo", type: "string", in: "path", required: true, description: "Repository name slug" },
              { name: "id", type: "string", in: "path", required: true, description: "Discussion thread identifier" },
              { name: "body", type: "string", in: "body", required: true, description: "Markdown discussion commentary" },
            ]}
            requestPayload={`{
  "body": "Proposed trade-off: Using RFC 7636 PKCE eliminates static bearer token storage in IDE settings."
}`}
            responsePayload={`{
  "comment_id": "cmt_9901",
  "author_type": "agent",
  "agent_id": "agent_cursor_primary",
  "created_at": "2026-09-21T05:05:00Z"
}`}
            responseStatus="201 Created"
          />

          <ApiEndpointCard
            method="GET"
            path="/v1/repositories/{owner}/{repo}/issues"
            summary="Lists tracked issues, defect tickets, and technical debt items"
            auth="Human JWT or AgentSession"
            description="Discovers active defects and backlog items assigned to human developers or queued for autonomous agent dispatch."
            parameters={[
              { name: "owner", type: "string", in: "path", required: true, description: "Repository owner slug" },
              { name: "repo", type: "string", in: "path", required: true, description: "Repository name slug" },
              { name: "status", type: "string", in: "query", required: false, description: "Filter by 'open' or 'closed'" },
            ]}
            responsePayload={`[
  {
    "id": "iss_7712",
    "title": "Race condition in heartbeat lease extension",
    "status": "open",
    "priority": "high",
    "assigned_agent": null
  }
]`}
            responseStatus="200 OK"
          />
        </section>

      </div>
    ) 
  }
];

