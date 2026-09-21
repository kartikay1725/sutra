import React from 'react';
import { DocSection } from './data';
import { PRReviewStateGraph, CIPipelineGraph } from '@/components/docs_graph_flows';
import { ShieldCheck, GitPullRequest, Eye, CheckCircle2, GitBranch } from 'lucide-react';
import { DocsHeading, DocsCallout } from '@/components/docs_components';

export const Group3HumanGuide: DocSection[] = [
  { 
    id: "human-guide", 
    category: "Engineering Workflow", 
    title: "Repositories, Changes & Reviews", 
    toc: [
      { id: "human-governance", label: "Human Governance & Ownership" },
      { id: "pr-lifecycle", label: "Pull Request Lifecycle & State Machine" },
      { id: "ci-pipeline", label: "Automated CI & Gatekeeper Pipeline" },
      { id: "branch-policies", label: "Branch Protection & Governance Policies" },
    ],
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Human Guide Overview */}
        <section>
          <DocsHeading id="human-governance" level={2}>
            Human User Governance & Ownership
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            As a human user in SUTRA, you possess ownership privileges. You act as the ultimate policy-maker, reviewer, and merger.
          </p>

          <table className="table" style={{ margin: "16px 0" }}>
            <thead>
              <tr>
                <th>ACTOR ROLE</th>
                <th>REPOSITORY ACCESS</th>
                <th>PR ACTIONS</th>
                <th>MERGE CAPABILITY</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 700, color: "#F5F5F5" }}>Owner</td>
                <td>Full governance, deletion & agent delegation</td>
                <td>Create, review, approve, resolve threads</td>
                <td style={{ color: "#3B82F6", fontWeight: 700 }}>✓ Allowed</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#3B82F6" }}>Collaborator</td>
                <td>Read, branch & push</td>
                <td>Create, comment & review</td>
                <td style={{ color: "#3B82F6", fontWeight: 700 }}>✓ When authorized</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#F97316" }}>AI Agent</td>
                <td>Bounded clone & push to feature branch</td>
                <td>Create PR & submit findings</td>
                <td style={{ color: "#8B949E", fontWeight: 700 }}>✕ Blocked</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Changes vs PRs */}
        <section>
          <DocsHeading id="pr-lifecycle" level={2}>
            Pull Request Lifecycle & State Machine
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA tracks changes through an authoritative review state machine. Merging is strictly locked until all active review threads are resolved and branch protections are satisfied.
          </p>

          <PRReviewStateGraph />

          <table className="table" style={{ marginTop: 20 }}>
            <thead>
              <tr>
                <th>CONCEPT</th>
                <th>AUTHORITATIVE ROLE</th>
                <th>EVIDENCE RECORDED</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 700, color: "#F5F5F5" }}>Commit</td>
                <td>Git tree snapshot</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#3B82F6" }}>SHA, Author, Tree</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#3B82F6" }}>Change</td>
                <td>Abstract work block</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#3B82F6" }}>Additions, Deletions, File-diffs</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#F97316" }}>Pull Request</td>
                <td>Formal merge request</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#3B82F6" }}>Reviews, CI status, Approvals</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* CI & Branch Protection */}
        <section>
          <DocsHeading id="ci-pipeline" level={2}>
            Automated CI & Gatekeeper Pipeline
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            CI jobs run against the specific commit SHA of the Change. Branch Protection acts as the ultimate gatekeeper for merges.
          </p>

          <CIPipelineGraph />
        </section>

        {/* Repository Settings & Branch Protection Policies */}
        <section>
          <DocsHeading id="branch-policies" level={2}>
            Repository Branch Protection & Governance Policies
          </DocsHeading>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            Repository policies are configured per-repository under <code style={{ color: "#F97316" }}>/repositories/[name]/settings</code>.
            Governance rules enforce organizational engineering standards:
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14, marginTop: 16 }}>
            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 6 }}>
                <ShieldCheck size={16} />
                Branch Protection Rules
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Configure branch patterns (e.g. <code style={{ color: "#F97316" }}>main</code>, <code style={{ color: "#F97316" }}>release/*</code>) with required approval counts, mandatory passing CI status checks, and linear git history requirements.
              </p>
            </div>

            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#3B82F6", fontWeight: 700, marginBottom: 6 }}>
                <GitPullRequest size={16} />
                Human Merge Hand-off
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                AI agents can never bypass branch protection or merge their own pull requests. When ready, agents call <code style={{ color: "#F97316" }}>sutra_request_merge</code> to transition the PR to a human approval queue.
              </p>
            </div>

            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 6 }}>
                <GitBranch size={16} />
                Universal GitHub Synchronization
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Repositories and upstream GitHub status are synchronized directly from the global Topbar sync button or the Repositories overview (<code style={{ color: "#F97316" }}>/repositories</code>). Automatic 5-minute debouncing prevents API rate limits with optional Force Sync.
              </p>
            </div>
          </div>
        </section>
      </div>
    )
  }
];
