'use client';

import React, { useState } from 'react';
import { I } from '../lib/icons';
import {
  SUTRA_CANONICAL_INSTRUCTION_BLOCK,
  SUTRA_INSTRUCTION_BLOCK_ID,
  SUTRA_INSTRUCTION_VERSION,
  SUTRA_SUPPORTED_TARGETS,
  SUTRA_RECOMMENDED_FILE,
} from '../lib/sutra-instructions';

export interface SutraAgentInstructionsProps {
  compact?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function SutraAgentInstructions({
  compact = false,
  className = '',
  style,
}: SutraAgentInstructionsProps) {
  const [copied, setCopied] = useState(false);
  const [selectedTarget, setSelectedTarget] = useState<string>(SUTRA_RECOMMENDED_FILE);
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleCopy = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(SUTRA_CANONICAL_INSTRUCTION_BLOCK);
      }
      setCopied(true);
      setShowConfirmation(true);
      setTimeout(() => setCopied(false), 2500);
      setTimeout(() => setShowConfirmation(false), 3500);
    } catch (err) {
      console.error('Failed to copy SUTRA agent instructions:', err);
    }
  };

  return (
    <section
      className={`sutra-agent-instructions-section ${className}`}
      style={{
        border: '1px solid #212836',
        borderRadius: 12,
        background: '#10151C',
        padding: compact ? '20px' : '24px 28px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        ...style,
      }}
      aria-labelledby="sutra-instructions-title"
    >
      {/* Header with Title and Optional Badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: '#171D26',
              border: '1px solid #2B3545',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38BDF8',
            }}
          >
            <I.FileCode2 size={18} />
          </div>
          <div>
            <h3
              id="sutra-instructions-title"
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: '#F2F5F8',
                margin: 0,
                letterSpacing: '-0.01em',
              }}
            >
              SUTRA Agent Instructions
            </h3>
            <div style={{ fontSize: 12, color: '#64748B', marginTop: 2 }}>
              Block ID: <code style={{ color: '#94A3B8' }}>{SUTRA_INSTRUCTION_BLOCK_ID}</code> · Version: <code style={{ color: '#94A3B8' }}>{`v${SUTRA_INSTRUCTION_VERSION}`}</code>
            </div>
          </div>
        </div>

        {/* Badge / Label */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(56, 189, 248, 0.1)',
            color: '#38BDF8',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            padding: '4px 10px',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.01em',
          }}
        >
          <I.Info size={13} />
          Optional but recommended
        </span>
      </div>

      {/* Explanatory Copy */}
      <div style={{ color: '#A8B1BD', fontSize: 13, lineHeight: 1.6 }}>
        <p style={{ margin: '0 0 8px' }}>
          MCP makes SUTRA available to your coding agent.
          For more reliable tool selection on this repository,
          we recommend adding the SUTRA instruction block to your
          existing <strong style={{ color: '#F2F5F8' }}>AGENTS.md</strong>,{' '}
          <strong style={{ color: '#F2F5F8' }}>CLAUDE.md</strong>,{' '}
          <strong style={{ color: '#F2F5F8' }}>Cursor Rules</strong>, or equivalent
          repository instruction file.
        </p>

        {/* Conceptual Distinction Note */}
        <div
          style={{
            background: '#090C10',
            border: '1px solid #1C2330',
            borderLeft: '3px solid #3B82F6',
            borderRadius: '0 8px 8px 0',
            padding: '10px 14px',
            margin: '8px 0 12px',
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontWeight: 600, color: '#F2F5F8', marginBottom: 4 }}>
            Understanding MCP vs. Instruction Files
          </div>
          <div>
            <strong style={{ color: '#38BDF8' }}>MCP</strong> provides harness-level availability of SUTRA tools across your IDE.
            <br />
            <strong style={{ color: '#38BDF8' }}>Repository instruction files</strong> provide optional repository-level behavioral guidance
            that helps coding agents consistently choose SUTRA for governed engineering tasks over generic git commands.
            <div style={{ color: '#64748B', marginTop: 4 }}>
              Note: SUTRA functions autonomously via MCP. An instruction file is never an absolute requirement for SUTRA operation.
            </div>
          </div>
        </div>

        {/* Non-destructive append note */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: '#E2E8F0',
            background: 'rgba(255, 255, 255, 0.03)',
            padding: '8px 12px',
            borderRadius: 6,
            border: '1px solid #212836',
          }}
        >
          <I.AlertCircle size={14} style={{ color: '#F59E0B', flexShrink: 0 }} />
          <span>
            If you already have an agent instruction file, add only the SUTRA block. Do not replace your existing instructions.
          </span>
        </div>
      </div>

      {/* Target Selector Tabs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#CBD5E1' }}>
            Placement Target:
          </label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {SUTRA_SUPPORTED_TARGETS.map((target) => (
              <button
                key={target.name}
                type="button"
                onClick={() => setSelectedTarget(target.name)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: selectedTarget === target.name ? 600 : 400,
                  background: selectedTarget === target.name ? '#1E293B' : '#0B0F15',
                  color: selectedTarget === target.name ? '#38BDF8' : '#94A3B8',
                  border: selectedTarget === target.name ? '1px solid #38BDF8' : '1px solid #212836',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {target.name}
                {target.recommended && (
                  <span style={{ marginLeft: 4, fontSize: 10, color: '#10B981' }}>(Recommended)</span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div style={{ fontSize: 11, color: '#64748B' }}>
          {selectedTarget === 'AGENTS.md' && 'Recommended cross-agent standard. Place as ./AGENTS.md at the root of your repository.'}
          {selectedTarget === 'CLAUDE.md' && 'Add to your existing ./CLAUDE.md file without replacing existing project instructions.'}
          {selectedTarget === 'Cursor Rules' && 'Add as a rule in .cursorrules or create .cursor/rules/sutra-governance.mdc.'}
          {selectedTarget === 'Equivalent Instruction Files' && 'Append the SUTRA block inside any workspace instruction file used by your agent harness.'}
        </div>
      </div>

      {/* Code Viewer */}
      <div
        style={{
          border: '1px solid #212836',
          borderRadius: 8,
          background: '#090C10',
          overflow: 'hidden',
        }}
      >
        {/* Code Header Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 14px',
            background: '#141A23',
            borderBottom: '1px solid #212836',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: 12,
                fontWeight: 600,
                color: '#CBD5E1',
              }}
            >
              {selectedTarget === 'AGENTS.md' ? 'AGENTS.md' : selectedTarget === 'CLAUDE.md' ? 'CLAUDE.md' : selectedTarget === 'Cursor Rules' ? '.cursorrules' : 'AGENTS.md'}
            </span>
            <span
              style={{
                fontSize: 11,
                color: '#64748B',
                background: '#090C10',
                padding: '1px 6px',
                borderRadius: 4,
                border: '1px solid #1C2330',
              }}
            >
              Markdown
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {showConfirmation && (
              <span
                style={{
                  fontSize: 12,
                  color: '#34D399',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  animation: 'fadeIn 0.15s ease-in',
                }}
              >
                <I.Check size={13} /> Copied SUTRA agent instructions
              </span>
            )}

            <button
              type="button"
              onClick={handleCopy}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleCopy();
                }
              }}
              title="Copy SUTRA agent instructions"
              aria-label="Copy SUTRA agent instructions"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 12px',
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                background: copied ? 'rgba(16, 185, 129, 0.15)' : '#1E293B',
                border: copied ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid #2B3545',
                color: copied ? '#34D399' : '#F2F5F8',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {copied ? <I.Check size={13} /> : <I.Copy size={13} />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        </div>

        {/* Code Content */}
        <pre
          style={{
            margin: 0,
            padding: '16px',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            fontSize: 12,
            lineHeight: 1.6,
            color: '#CBD5E1',
            overflowX: 'auto',
            maxHeight: compact ? '260px' : '360px',
            whiteSpace: 'pre',
          }}
        >
          {SUTRA_CANONICAL_INSTRUCTION_BLOCK}
        </pre>
      </div>

      {/* Footer Safety Notice */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 11,
          color: '#64748B',
          marginTop: -4,
        }}
      >
        <I.ShieldCheck size={13} style={{ color: '#10B981', flexShrink: 0 }} />
        <span>
          Contains zero credentials, secrets, or environment-specific URLs. Safe to commit to public or private version control.
        </span>
      </div>
    </section>
  );
}
