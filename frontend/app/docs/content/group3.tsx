import React from 'react';
import { DocSection } from './data';
import { PRReviewStateGraph, CIPipelineGraph } from '@/components/docs_graph_flows';
import { ShieldCheck, GitPullRequest, Eye, CheckCircle2, GitBranch } from 'lucide-react';

export const Group3HumanGuide: DocSection[] = [
  { 
    id: "human-guide", 
    category: "Human Guide", 
    title: "Repositories, Changes & Reviews", 
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Human Guide Overview */}
        <section>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Human User Governance & Ownership
          </h2>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
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
                <td style={{ fontWeight: 700, color: "#F2F5F8" }}>Owner</td>
                <td>Full governance, deletion & agent delegation</td>
                <td>Create, review, approve, resolve threads</td>
                <td style={{ color: "#22C55E", fontWeight: 700 }}>✓ Allowed</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#60A5FA" }}>Collaborator</td>
                <td>Read, branch & push</td>
                <td>Create, comment & review</td>
                <td style={{ color: "#22C55E", fontWeight: 700 }}>✓ When authorized</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#818CF8" }}>AI Agent</td>
                <td>Bounded clone & push to feature branch</td>
                <td>Create PR & submit findings</td>
                <td style={{ color: "#EF4444", fontWeight: 700 }}>✕ Blocked</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Changes vs PRs */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Pull Request Lifecycle & State Machine
          </h3>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
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
                <td style={{ fontWeight: 700, color: "#F2F5F8" }}>Commit</td>
                <td>Git tree snapshot</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#60A5FA" }}>SHA, Author, Tree</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#60A5FA" }}>Change</td>
                <td>Abstract work block</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#60A5FA" }}>Additions, Deletions, File-diffs</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#818CF8" }}>Pull Request</td>
                <td>Formal merge request</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#60A5FA" }}>Reviews, CI status, Approvals</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* CI & Branch Protection */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Automated CI & Gatekeeper Pipeline
          </h3>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
            CI jobs run against the specific commit SHA of the Change. Branch Protection acts as the ultimate gatekeeper for merges.
          </p>

          <CIPipelineGraph />
        </section>
      </div>
    )
  }
];
