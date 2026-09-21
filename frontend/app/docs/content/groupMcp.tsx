import React from 'react';
import { DocSection } from './data';
import { SutraAgentInstructions } from '@/components/SutraAgentInstructions';
import { ShieldCheck, Cpu, Key, Lock, Terminal, Globe2, Book, CheckCircle2, RefreshCw, FolderGit2 } from 'lucide-react';
import { CANONICAL_MCP_ENDPOINT } from '@/components/sutra-connect';
import { DocsHeading } from '@/components/docs_components';

export const GroupMcpIntegration: DocSection[] = [
  {
    id: "mcp-integration",
    category: "MCP Integration",
    title: "MCP Integration & Agent Instructions",
    toc: [
      { id: "mcp-overview", label: "MCP Protocol & Integration" },
      { id: "agent-instructions", label: "SUTRA Agent Instructions" },
      { id: "engineering-boundary", label: "Engineering Boundary: Local Git vs. SUTRA" },
      { id: "tool-catalog", label: "Complete MCP Tool Catalog (21 Tools)" },
    ],
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Overview Section */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#F97316",
                background: "rgba(249, 115, 22, 0.1)",
                border: "1px solid rgba(249, 115, 22, 0.25)",
                padding: "2px 8px",
                borderRadius: 4,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Native Protocol
            </span>
            <span style={{ fontSize: 13, color: "#737373" }}>RFC 9728 / Streamable HTTP</span>
          </div>

          <DocsHeading id="mcp-overview" level={2}>
            Model Context Protocol (MCP) Integration
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA exposes an enterprise-grade <strong style={{ color: "#F5F5F5" }}>Model Context Protocol (MCP)</strong> server over Streamable HTTP.
            When connected, coding agents gain direct access to SUTRA governance tools, allowing them to claim tasks, declare changes, push cryptographic commits, and open pull requests.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 6 }}>
                <Globe2 size={16} />
                Endpoint URL
              </div>
              <code style={{ fontSize: 12, color: "#F97316", wordBreak: "break-all" }}>
                {CANONICAL_MCP_ENDPOINT}
              </code>
            </div>

            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#3B82F6", fontWeight: 700, marginBottom: 6 }}>
                <ShieldCheck size={16} />
                OAuth 2.1 PKCE
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", margin: 0 }}>
                Zero permanent tokens needed. Agents discover authorization endpoints dynamically.
              </p>
            </div>
          </div>
        </section>

        {/* CANONICAL SUTRA AGENT INSTRUCTIONS SECTION */}
        <div id="agent-instructions">
          <SutraAgentInstructions />
        </div>

        {/* Engineering Boundary Definition */}
        <section>
          <DocsHeading id="engineering-boundary" level={2}>
            Engineering Boundary: Local Git vs. SUTRA
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA does not replace local Git inspection or developer editing tools. SUTRA governs repository changes and code submission:
          </p>

          <table className="table" style={{ margin: "16px 0" }}>
            <thead>
              <tr>
                <th>DEVELOPMENT OPERATION</th>
                <th>APPROPRIATE TOOLING</th>
                <th>GOVERNANCE RULE</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 600, color: "#F5F5F5" }}>Reading & editing files</td>
                <td>IDE / Local File System</td>
                <td>Standard workspace editing.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F5F5F5" }}>Running tests & local builds</td>
                <td>Terminal / Test Runners</td>
                <td>Pre-commit verification in workspace.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F5F5F5" }}>Git inspection (diff, status, log)</td>
                <td>Terminal Git</td>
                <td>Workspace inspection allowed.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F97316" }}>Starting tasks & allocating branches</td>
                <td style={{ fontFamily: "monospace", color: "#F97316" }}>sutra_start_task</td>
                <td>Binds session lease to feature branch.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F97316" }}>Creating & pushing commits</td>
                <td style={{ fontFamily: "monospace", color: "#F97316" }}>sutra_push_commit</td>
                <td>Required for cryptographic provenance.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F97316" }}>Opening Pull Requests</td>
                <td style={{ fontFamily: "monospace", color: "#F97316" }}>sutra_open_pull_request</td>
                <td>Triggers CI checks & governance reviews.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F97316" }}>Requesting merge handover</td>
                <td style={{ fontFamily: "monospace", color: "#F97316" }}>sutra_request_merge</td>
                <td>Strict human approval required. Agents cannot merge.</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Complete SUTRA MCP Tool Catalog */}
        <section>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
            <DocsHeading id="tool-catalog" level={2} style={{ margin: 0 }}>
              Complete SUTRA MCP Tool Catalog (21 Available Tools)
            </DocsHeading>
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#3B82F6",
                background: "rgba(59, 130, 246, 0.1)",
                border: "1px solid rgba(59, 130, 246, 0.25)",
                padding: "2px 8px",
                borderRadius: 4,
              }}
            >
              Protocol v0.4.0
            </span>
          </div>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            Every tool is authenticated via SUTRA OAuth 2.1 PKCE or agent session bearer tokens. Intent mappings and parameters are strictly enforced:
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              {
                name: "sutra_get_context",
                phase: "Session Identity & Context",
                desc: "Discovers agent identity, assigned repository, capability grants, active lease, and current active task.",
                params: "None",
                intents: "'who am I', 'check permissions', 'check session'",
                isNew: false,
              },
              {
                name: "sutra_start_task",
                phase: "Task Claim & Allocation",
                desc: "Auto-creates or claims an engineering task from user prompt; allocates branch and locks lease. Do NOT ask user for task ID.",
                params: "prompt (required), repository_slug (optional), branch_name (optional)",
                intents: "'start working on this', 'fix this bug', 'implement feature'",
                isNew: false,
              },
              {
                name: "sutra_declare_change",
                phase: "Branch & Change Tracking",
                desc: "Allocates git feature branch, binds task lease, and registers tracked change record in SUTRA state machine.",
                params: "task_id (required), change_title (required), branch_name (required)",
                intents: "'track this change', 'start code change', 'allocate feature branch'",
                isNew: false,
              },
              {
                name: "sutra_push_commit",
                phase: "Cryptographic Code Submission",
                desc: "Submits modified files and commit message with SUTRA cryptographic author provenance. Replaces terminal git commit/git push.",
                params: "task_id (required), message (required), files (required array of {path, content})",
                intents: "'commit this', 'push this change', 'push commit'",
                isNew: false,
              },
              {
                name: "sutra_open_pull_request",
                phase: "Pull Request Lifecycle",
                desc: "Opens linked GitHub pull request and initiates automated CI checks and branch governance review.",
                params: "task_id (required), title (required), body (required), base_branch (optional)",
                intents: "'open a PR', 'create pull request', 'submit PR for review'",
                isNew: false,
              },
              {
                name: "sutra_get_status",
                phase: "Lifecycle Tracking",
                desc: "Queries real-time lifecycle status, active blockers, CI execution status, and review thread progress.",
                params: "task_id (optional), pr_id (optional), change_id (optional)",
                intents: "'what's the status?', 'where is my PR?', 'what's blocking?'",
                isNew: false,
              },
              {
                name: "sutra_get_governance",
                phase: "Merge Governance",
                desc: "Evaluates branch protection rules, required approval counts, CI status gates, and merge readiness.",
                params: "pr_id (required)",
                intents: "'can this merge?', 'why can't this merge?', 'is CI passing?'",
                isNew: false,
              },
              {
                name: "sutra_request_merge",
                phase: "Human Hand-off",
                desc: "Submits merge request evaluation and queues PR for human owner sign-off. AI agents cannot merge directly.",
                params: "pr_id (required), merge_method (optional: 'merge', 'squash', 'rebase')",
                intents: "'request merge', 'ready to merge', 'handover for merge'",
                isNew: false,
              },
              {
                name: "sutra_get_provenance",
                phase: "Cryptographic Auditing",
                desc: "Returns cryptographic attribution and author provenance for specific commit SHAs, tasks, or changes.",
                params: "commit_sha (optional), change_id (optional)",
                intents: "'who wrote this commit?', 'check commit provenance'",
                isNew: false,
              },
              {
                name: "sutra_complete_task",
                phase: "Task Finalization",
                desc: "Records implementation summary, test verification evidence, and artifact outputs to finalize the task.",
                params: "task_id (required), execution_summary (required), validation_notes (optional)",
                intents: "'finish the task', 'mark task complete', 'summarize validation'",
                isNew: false,
              },
              {
                name: "sutra_search_knowledge",
                phase: "Code Intelligence",
                desc: "Performs semantic and AST architecture search across repository codebase graph and symbol dependency tree.",
                params: "repository_id (required), query (required), limit (optional)",
                intents: "'search codebase', 'find symbol', 'explore dependencies'",
                isNew: false,
              },
              {
                name: "sutra_create_issue",
                phase: "Issue & Defect Logging",
                desc: "Creates a tracked GitHub issue or logs technical debt linked to the current task context.",
                params: "task_id (required), title (required), body (required)",
                intents: "'file a bug', 'create issue', 'report technical debt'",
                isNew: false,
              },
              {
                name: "sutra_list_issues",
                phase: "Backlog Discovery",
                desc: "Lists tracked issues for a repository to discover backlog items and open defect tickets.",
                params: "repository_id (required), state (optional), limit (optional)",
                intents: "'list issues', 'what bugs are open', 'check backlog'",
                isNew: true,
              },
              {
                name: "sutra_create_discussion",
                phase: "Architectural Collaboration",
                desc: "Starts an architectural discussion or RFC on the repository linked to the active task with verifiable agent provenance.",
                params: "task_id (required), title (required), body (required), category (optional)",
                intents: "'propose RFC', 'start discussion', 'ask architecture question'",
                isNew: true,
              },
              {
                name: "sutra_list_discussions",
                phase: "Discussion Exploration",
                desc: "Lists architectural discussions and RFC threads for a repository.",
                params: "repository_id (required), category (optional), limit (optional)",
                intents: "'list discussions', 'browse RFCs'",
                isNew: true,
              },
              {
                name: "sutra_comment_discussion",
                phase: "Discussion Participation",
                desc: "Posts an informed architectural comment to a discussion thread with verified agent identity.",
                params: "discussion_id (required), body (required)",
                intents: "'comment on RFC', 'reply to discussion'",
                isNew: true,
              },
              {
                name: "sutra_get_ci_logs",
                phase: "CI Diagnosis",
                desc: "Retrieves logs and failure traces from CI runs to diagnose test errors.",
                params: "pr_id (required), job_id (optional)",
                intents: "'why did CI fail', 'get test logs', 'check build output'",
                isNew: true,
              },
              {
                name: "sutra_get_pr_comments",
                phase: "Review Feedback",
                desc: "Retrieves reviewer feedback, inline comments, and change requests on a pull request.",
                params: "pr_id (required)",
                intents: "'what did reviewers say', 'get PR comments', 'check review feedback'",
                isNew: true,
              },
              {
                name: "sutra_add_pr_comment",
                phase: "Review Response",
                desc: "Adds a clarifying comment or responds to reviewer feedback on a pull request.",
                params: "pr_id (required), body (required)",
                intents: "'respond to review', 'comment on PR'",
                isNew: true,
              },
              {
                name: "sutra_clone_repository",
                phase: "Repository Management",
                desc: "Clones any external Git URL or GitHub repository into SUTRA managed bare storage, installs pre-receive hooks, and indexes Knowledge Graph.",
                params: "url (required), name (optional), description (optional), visibility (optional)",
                intents: "'clone a repo', 'clone repository', 'import git repository'",
                isNew: false,
              },
              {
                name: "sutra_import_external_change",
                phase: "External Ingestion",
                desc: "Ingests external commits or GitHub PRs created outside SUTRA into the governed change tracking system.",
                params: "repository_slug (required), git_ref (required)",
                intents: "'import external commit', 'sync outside PR'",
                isNew: false,
              },
            ].map((tool) => (
              <div
                key={tool.name}
                style={{
                  padding: 16,
                  border: tool.isNew ? "1px solid rgba(249, 115, 22, 0.4)" : "1px solid #242424",
                  borderRadius: 10,
                  background: tool.isNew ? "rgba(249, 115, 22, 0.05)" : "#151515",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6, flexWrap: "wrap", gap: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <code style={{ fontSize: 13, fontWeight: 700, color: "#F97316" }}>
                      {tool.name}
                    </code>
                    {tool.isNew && (
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#F97316",
                          background: "rgba(249, 115, 22, 0.15)",
                          border: "1px solid rgba(249, 115, 22, 0.3)",
                          padding: "1px 6px",
                          borderRadius: 4,
                          textTransform: "uppercase",
                        }}
                      >
                        Newly Added
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: 11, color: "#737373", fontWeight: 600 }}>
                    {tool.phase}
                  </span>
                </div>

                <p style={{ fontSize: 13, color: "#A3A3A3", margin: "0 0 8px 0", lineHeight: 1.5 }}>
                  {tool.desc}
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
                  <div style={{ color: "#737373" }}>
                    <strong style={{ color: "#A3A3A3" }}>Parameters: </strong>
                    <code style={{ color: "#F5F5F5" }}>{tool.params}</code>
                  </div>
                  <div style={{ color: "#737373" }}>
                    <strong style={{ color: "#A3A3A3" }}>Sample Intents: </strong>
                    <span style={{ fontStyle: "italic", color: "#A3A3A3" }}>{tool.intents}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Platform Architecture Updates */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 14 }}>
            Platform Architecture & Governance Updates
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 8 }}>
                <RefreshCw size={16} />
                Dual GitHub Synchronization
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                GitHub repository sync is now permanently accessible directly from the global Topbar header (compact dropdown with live connection details) and the Repositories overview (<code style={{ color: "#F97316" }}>/repositories</code>). Features an automatic 5-minute debounced cooldown with an on-demand Force Sync button to bypass cooldowns.
              </p>
            </div>

            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#3B82F6", fontWeight: 700, marginBottom: 8 }}>
                <ShieldCheck size={16} />
                Repository-Scoped Policy Controls
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                The legacy global settings page has been deprecated and removed. All branch protection rules, review requirements, merge policies, and repository parameters are now managed contextually per repository at <code style={{ color: "#F97316" }}>/repositories/[name]/settings</code>.
              </p>
            </div>

            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 8 }}>
                <Terminal size={16} />
                Task Lifecycle & Confirmation Guards
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Agent task counters and execution metrics update in real-time. Terminating an agent task decrements running counters immediately with guarded confirmation modals to prevent accidental task disruptions.
              </p>
            </div>

            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#3B82F6", fontWeight: 700, marginBottom: 8 }}>
                <FolderGit2 size={16} />
                Native GitHub Clone Interoperability
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Clone links throughout the dashboard and repository headers provide authentic GitHub URLs for developer workstations and coding agents, while SUTRA MCP governs remote commits and PR lifecycles.
              </p>
            </div>
          </div>
        </section>

        {/* Client Setup Snippets */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            Client Configuration
          </h3>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            Add SUTRA to your agent configuration file:
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#0B0B0B" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#F5F5F5" }}>Cursor (~/.cursor/mcp.json)</span>
                <span style={{ fontSize: 11, color: "#737373" }}>JSON</span>
              </div>
              <pre style={{ margin: 0, fontFamily: "monospace", fontSize: 12, color: "#F97316" }}>
{`{
  "mcpServers": {
    "sutra": {
      "url": "${CANONICAL_MCP_ENDPOINT}"
    }
  }
}`}
              </pre>
            </div>

            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#0B0B0B" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#F5F5F5" }}>Claude Code (Terminal)</span>
                <span style={{ fontSize: 11, color: "#737373" }}>CLI</span>
              </div>
              <pre style={{ margin: 0, fontFamily: "monospace", fontSize: 12, color: "#F97316" }}>
{`claude mcp add --transport http sutra ${CANONICAL_MCP_ENDPOINT}`}
              </pre>
            </div>
          </div>
        </section>
      </div>
    )
  }
];
