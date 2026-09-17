import React from 'react';
import { DocSection } from './data';

export const Group8Reference: DocSection[] = [
  { 
    id: "reference", 
    category: "Reference", 
    title: "Reference", 
    content: (
      <div className="flex flex-col gap-10">
        <section>
          <h2 className="text-xl font-bold mb-4">Engineering Lifecycle & States</h2>
          <table className="table mt-4">
            <thead>
              <tr>
                <th>STATE</th>
                <th>MEANING</th>
                <th>ALLOWED NEXT STATES</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-xs">Open</td>
                <td>PR is actively being worked on.</td>
                <td>Reviewing, Closed</td>
              </tr>
              <tr>
                <td className="font-mono text-xs">Reviewing</td>
                <td>Human/Agent is reviewing code.</td>
                <td>Approved, Blocked (Changes Requested)</td>
              </tr>
              <tr>
                <td className="font-mono text-xs">Merged</td>
                <td>Cryptographic merge executed.</td>
                <td>Terminal state.</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Terminology</h3>
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="font-bold text-[var(--accent)]">Actor vs User</h4>
              <p className="text-sm opacity-80 mt-1">A User is a human database identity. An Actor is the runtime security context that SUTRA uses to authorize API calls. Agents have Actors but are not Users.</p>
            </div>
            <div>
              <h4 className="font-bold text-[var(--accent)]">Commit vs Change</h4>
              <p className="text-sm opacity-80 mt-1">A Commit is raw Git data. A Change is a SUTRA entity that links commits to PRs, Reviews, and CI Jobs.</p>
            </div>
          </div>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Current Limitations</h3>
          <p className="mb-4">This section outlines brutally honest limitations in the current implementation to maintain trust.</p>
          <table className="table mt-4">
            <thead>
              <tr>
                <th>CAPABILITY</th>
                <th>STATUS</th>
                <th>LIMITATION</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-xs text-yellow-300">Agent Token Rotation</td>
                <td>API ONLY</td>
                <td>No UI currently exists in the dashboard to rotate tokens. You must use the API.</td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-yellow-300">WebAuthn</td>
                <td>NOT CURRENTLY AVAILABLE</td>
                <td>Hardware keys are not yet supported for login.</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    ) 
  }
];
