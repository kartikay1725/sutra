import React from 'react';
import { DocSection } from './data';
import { SutraAgentInstructions } from '@/components/SutraAgentInstructions';
import { ShieldCheck, Cpu, Key, Lock, Terminal, Globe2, Book, CheckCircle2 } from 'lucide-react';
import { CANONICAL_MCP_ENDPOINT } from '@/components/sutra-connect';

export const GroupMcpIntegration: DocSection[] = [
  {
    id: "mcp-integration",
    category: "MCP Integration",
    title: "MCP Integration & Agent Instructions",
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Overview Section */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#38BDF8",
                background: "rgba(56, 189, 248, 0.1)",
                border: "1px solid rgba(56, 189, 248, 0.25)",
                padding: "2px 8px",
                borderRadius: 4,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Native Protocol
            </span>
            <span style={{ fontSize: 13, color: "#64748B" }}>RFC 9728 / Streamable HTTP</span>
          </div>

          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Model Context Protocol (MCP) Integration
          </h2>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA exposes an enterprise-grade <strong style={{ color: "#F2F5F8" }}>Model Context Protocol (MCP)</strong> server over Streamable HTTP.
            When connected, coding agents gain direct access to SUTRA governance tools, allowing them to claim tasks, declare changes, push cryptographic commits, and open pull requests.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
            <div style={{ padding: 16, border: "1px solid #212836", borderRadius: 8, background: "#10151C" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#38BDF8", fontWeight: 700, marginBottom: 6 }}>
                <Globe2 size={16} />
                Endpoint URL
              </div>
              <code style={{ fontSize: 12, color: "#38BDF8", wordBreak: "break-all" }}>
                {CANONICAL_MCP_ENDPOINT}
              </code>
            </div>

            <div style={{ padding: 16, border: "1px solid #212836", borderRadius: 8, background: "#10151C" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#10B981", fontWeight: 700, marginBottom: 6 }}>
                <ShieldCheck size={16} />
                OAuth 2.1 PKCE
              </div>
              <p style={{ fontSize: 12, color: "#A8B1BD", margin: 0 }}>
                Zero permanent tokens needed. Agents discover authorization endpoints dynamically.
              </p>
            </div>
          </div>
        </section>

        {/* CANONICAL SUTRA AGENT INSTRUCTIONS SECTION */}
        <SutraAgentInstructions />

        {/* Engineering Boundary Definition */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Engineering Boundary: Local Git vs. SUTRA
          </h3>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
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
                <td style={{ fontWeight: 600, color: "#F2F5F8" }}>Reading & editing files</td>
                <td>IDE / Local File System</td>
                <td>Standard workspace editing.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F2F5F8" }}>Running tests & local builds</td>
                <td>Terminal / Test Runners</td>
                <td>Pre-commit verification in workspace.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#F2F5F8" }}>Git inspection (diff, status, log)</td>
                <td>Terminal Git</td>
                <td>Workspace inspection allowed.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#38BDF8" }}>Starting tasks & allocating branches</td>
                <td style={{ fontFamily: "monospace", color: "#38BDF8" }}>sutra_start_task</td>
                <td>Binds session lease to feature branch.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#38BDF8" }}>Creating & pushing commits</td>
                <td style={{ fontFamily: "monospace", color: "#38BDF8" }}>sutra_push_commit</td>
                <td>Required for cryptographic provenance.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#38BDF8" }}>Opening Pull Requests</td>
                <td style={{ fontFamily: "monospace", color: "#38BDF8" }}>sutra_open_pull_request</td>
                <td>Triggers CI checks & governance reviews.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600, color: "#38BDF8" }}>Requesting merge handover</td>
                <td style={{ fontFamily: "monospace", color: "#38BDF8" }}>sutra_request_merge</td>
                <td>Strict human approval required. Agents cannot merge.</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Client Setup Snippets */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Client Configuration
          </h3>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
            Add SUTRA to your agent configuration file:
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ padding: 16, border: "1px solid #212836", borderRadius: 8, background: "#090C10" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#CBD5E1" }}>Cursor (~/.cursor/mcp.json)</span>
                <span style={{ fontSize: 11, color: "#64748B" }}>JSON</span>
              </div>
              <pre style={{ margin: 0, fontFamily: "monospace", fontSize: 12, color: "#38BDF8" }}>
{`{
  "mcpServers": {
    "sutra": {
      "url": "${CANONICAL_MCP_ENDPOINT}"
    }
  }
}`}
              </pre>
            </div>

            <div style={{ padding: 16, border: "1px solid #212836", borderRadius: 8, background: "#090C10" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#CBD5E1" }}>Claude Code (Terminal)</span>
                <span style={{ fontSize: 11, color: "#64748B" }}>CLI</span>
              </div>
              <pre style={{ margin: 0, fontFamily: "monospace", fontSize: 12, color: "#38BDF8" }}>
{`claude mcp add --transport http sutra ${CANONICAL_MCP_ENDPOINT}`}
              </pre>
            </div>
          </div>
        </section>
      </div>
    )
  }
];
