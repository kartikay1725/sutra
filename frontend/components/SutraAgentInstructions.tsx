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
        border: '1px solid #E2E8F0',
        borderRadius: 12,
        background: '#FFFFFF',
        padding: compact ? '20px' : '24px 28px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
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
              background: '#FFF7ED',
              border: '1px solid #FFEDD5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#EA580C',
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
                color: '#0F172A',
                margin: 0,
                letterSpacing: '-0.01em',
              }}
            >
              SUTRA Agent Instructions
            </h3>
            <div style={{ fontSize: 12, color: '#64748B', marginTop: 2 }}>
              Block ID: <code style={{ color: '#0F172A', background: '#F1F5F9', padding: '1px 5px', borderRadius: 4, border: '1px solid #E2E8F0' }}>{SUTRA_INSTRUCTION_BLOCK_ID}</code> · Version: <code style={{ color: '#0F172A', background: '#F1F5F9', padding: '1px 5px', borderRadius: 4, border: '1px solid #E2E8F0' }}>{`v${SUTRA_INSTRUCTION_VERSION}`}</code>
            </div>
          </div>
        </div>

        {/* Badge / Label */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(234, 88, 12, 0.08)',
            color: '#EA580C',
            border: '1px solid rgba(234, 88, 12, 0.25)',
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
      <div style={{ color: '#334155', fontSize: 13, lineHeight: 1.6 }}>
        <p style={{ margin: '0 0 8px' }}>
          MCP makes SUTRA available to your coding agent.
          For more reliable tool selection on this repository,
          we recommend adding the SUTRA instruction block to your
          existing <strong style={{ color: '#0F172A' }}>AGENTS.md</strong>,{' '}
          <strong style={{ color: '#0F172A' }}>CLAUDE.md</strong>,{' '}
          <strong style={{ color: '#0F172A' }}>Cursor Rules</strong>, or equivalent
          repository instruction file.
        </p>

        {/* Conceptual Distinction Note */}
        <div
          style={{
            background: '#F8FAFC',
            border: '1px solid #E2E8F0',
            borderLeft: '3px solid #EA580C',
            borderRadius: '0 8px 8px 0',
            padding: '10px 14px',
            margin: '8px 0 12px',
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontWeight: 700, color: '#0F172A', marginBottom: 4 }}>
            Understanding MCP vs. Instruction Files
          </div>
          <div style={{ color: '#475569' }}>
            <strong style={{ color: '#EA580C' }}>MCP</strong> provides harness-level availability of SUTRA tools across your IDE.
            <br />
            <strong style={{ color: '#EA580C' }}>Repository instruction files</strong> provide optional repository-level behavioral guidance
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
            color: '#9A3412',
            background: '#FFF7ED',
            padding: '8px 12px',
            borderRadius: 6,
            border: '1px solid #FFEDD5',
          }}
        >
          <I.AlertCircle size={14} style={{ color: '#EA580C', flexShrink: 0 }} />
          <span>
            If you already have an agent instruction file, add only the SUTRA block. Do not replace your existing instructions.
          </span>
        </div>
      </div>

      {/* Target Selector Tabs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 700, color: '#0F172A' }}>
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
                  fontWeight: selectedTarget === target.name ? 700 : 500,
                  background: selectedTarget === target.name ? 'rgba(234, 88, 12, 0.1)' : '#F8FAFC',
                  color: selectedTarget === target.name ? '#EA580C' : '#475569',
                  border: selectedTarget === target.name ? '1px solid #EA580C' : '1px solid #E2E8F0',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {target.name}
                {target.recommended && (
                  <span style={{ marginLeft: 4, fontSize: 10, color: '#2563EB' }}>(Recommended)</span>
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
          border: '1px solid #27272A',
          borderRadius: 8,
          background: '#09090B',
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
            background: '#18181B',
            borderBottom: '1px solid #27272A',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: 12,
                fontWeight: 600,
                color: '#F4F4F5',
              }}
            >
              {selectedTarget === 'AGENTS.md' ? 'AGENTS.md' : selectedTarget === 'CLAUDE.md' ? 'CLAUDE.md' : selectedTarget === 'Cursor Rules' ? '.cursorrules' : 'AGENTS.md'}
            </span>
            <span
              style={{
                fontSize: 11,
                color: '#A1A1AA',
                background: '#27272A',
                padding: '1px 6px',
                borderRadius: 4,
                border: '1px solid #3F3F46',
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
                background: copied ? 'rgba(16, 185, 129, 0.15)' : '#27272A',
                border: copied ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid #3F3F46',
                color: copied ? '#34D399' : '#F4F4F5',
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
            fontFamily: 'JetBrains Mono, Menlo, monospace',
            fontSize: 12,
            lineHeight: 1.6,
            color: '#E4E4E7',
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
          fontSize: 11.5,
          color: '#64748B',
          marginTop: -4,
        }}
      >
        <I.ShieldCheck size={14} style={{ color: '#2563EB', flexShrink: 0 }} />
        <span>
          Contains zero credentials, secrets, or environment-specific URLs. Safe to commit to public or private version control.
        </span>
      </div>
    </section>
  );
}
