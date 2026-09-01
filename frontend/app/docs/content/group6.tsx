import React from 'react';
import { DocSection } from './data';

export const Group6APIReference: DocSection[] = [
  { 
    id: "api-reference", 
    category: "API Reference", 
    title: "API Reference", 
    content: (
      <div className="flex flex-col gap-10">
        
        <section>
          <h2 className="text-xl font-bold mb-4">API Overview</h2>
          <p className="mb-4">These endpoints represent the authoritative API boundaries for authentication, agent operations, and repository management. Do not attempt to guess or brute-force endpoints.</p>
        </section>
        
        <section>
          <h3 className="text-lg font-bold mb-4">Authentication & Agent APIs</h3>
          <div className="flex flex-col gap-4">
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-green-500/20 text-green-400 border border-green-500/50 text-xs font-bold px-2 py-1 rounded mr-3">POST</span>
                <code className="text-sm">/v1/auth/login</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Authenticates human credentials and issues a JWT token.</p>
              <p className="text-xs opacity-70"><strong>Auth:</strong> None (Public)</p>
            </div>

            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-blue-500/20 text-blue-400 border border-blue-500/50 text-xs font-bold px-2 py-1 rounded mr-3">GET</span>
                <code className="text-sm">/v1/me</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Retrieves the current authenticated profile (Human or Agent).</p>
              <p className="text-xs opacity-70"><strong>Auth:</strong> JWT (Human) or Basic Auth (Agent)</p>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-green-500/20 text-green-400 border border-green-500/50 text-xs font-bold px-2 py-1 rounded mr-3">POST</span>
                <code className="text-sm">/v1/agents/session</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Exchanges a long-lived Agent Credential for a short-lived, authenticated AgentSession token.</p>
              <p className="text-xs opacity-70"><strong>Auth:</strong> Long-lived Agent Credential</p>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-green-500/20 text-green-400 border border-green-500/50 text-xs font-bold px-2 py-1 rounded mr-3">POST</span>
                <code className="text-sm">/v1/agent-protocol/handshake</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Initial discovery endpoint for an external AI agent to declare intent and retrieve the SUTRA Agent Protocol workflow.</p>
              <p className="text-xs opacity-70"><strong>Auth:</strong> None (Public)</p>
            </div>

            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-green-500/20 text-green-400 border border-green-500/50 text-xs font-bold px-2 py-1 rounded mr-3">POST</span>
                <code className="text-sm">/v1/agent-protocol/poll</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Polling endpoint for authenticated agents to receive deterministic, machine-readable instructions (e.g., capability discovery).</p>
              <p className="text-xs opacity-70"><strong>Auth:</strong> AgentSession Token (Bearer)</p>
            </div>
          </div>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Repository & Change APIs</h3>
          <div className="flex flex-col gap-4">
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-blue-500/20 text-blue-400 border border-blue-500/50 text-xs font-bold px-2 py-1 rounded mr-3">GET</span>
                <code className="text-sm">/v1/repositories</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Lists all repositories the authenticated actor has explicit access to.</p>
            </div>

            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <div className="flex items-center mb-2">
                <span className="bg-green-500/20 text-green-400 border border-green-500/50 text-xs font-bold px-2 py-1 rounded mr-3">POST</span>
                <code className="text-sm">/v1/repositories/&#123;owner&#125;/&#123;repo&#125;/changes</code>
              </div>
              <p className="text-xs opacity-70 mb-2"><strong>Purpose:</strong> Agents create a Change after completing a repository modification so the work can enter SUTRA's review lifecycle.</p>
              <p className="text-xs opacity-70"><strong>Capability Required:</strong> <code>change.create</code></p>
            </div>
          </div>
        </section>

      </div>
    ) 
  }
];
