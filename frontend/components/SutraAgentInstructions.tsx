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
        border: '1px solid #242424',
        borderRadius: 12,
        background: '#151515',
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
              background: '#1C1C1C',
              border: '1px solid #242424',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#F97316',
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
                color: '#F5F5F5',
                margin: 0,
                letterSpacing: '-0.01em',
              }}
            >
              SUTRA Agent Instructions
            </h3>
            <div style={{ fontSize: 12, color: '#737373', marginTop: 2 }}>
              Block ID: <code style={{ color: '#A3A3A3' }}>{SUTRA_INSTRUCTION_BLOCK_ID}</code> · Version: <code style={{ color: '#A3A3A3' }}>{`v${SUTRA_INSTRUCTION_VERSION}`}</code>
            </div>
          </div>
        </div>

        {/* Badge / Label */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(249, 115, 22, 0.1)',
            color: '#F97316',
            border: '1px solid rgba(249, 115, 22, 0.25)',
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
      <div style={{ color: '#A3A3A3', fontSize: 13, lineHeight: 1.6 }}>
        <p style={{ margin: '0 0 8px' }}>
          MCP makes SUTRA available to your coding agent.
          For more reliable tool selection on this repository,
          we recommend adding the SUTRA instruction block to your
          existing <strong style={{ color: '#F5F5F5' }}>AGENTS.md</strong>,{' '}
          <strong style={{ color: '#F5F5F5' }}>CLAUDE.md</strong>,{' '}
          <strong style={{ color: '#F5F5F5' }}>Cursor Rules</strong>, or equivalent
          repository instruction file.
        </p>

        {/* Conceptual Distinction Note */}
        <div
          style={{
            background: '#0B0B0B',
            border: '1px solid #242424',
            borderLeft: '3px solid #F97316',
            borderRadius: '0 8px 8px 0',
            padding: '10px 14px',
            margin: '8px 0 12px',
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontWeight: 600, color: '#F5F5F5', marginBottom: 4 }}>
            Understanding MCP vs. Instruction Files
          </div>
          <div>
            <strong style={{ color: '#F97316' }}>MCP</strong> provides harness-level availability of SUTRA tools across your IDE.
            <br />
            <strong style={{ color: '#F97316' }}>Repository instruction files</strong> provide optional repository-level behavioral guidance
            that helps coding agents consistently choose SUTRA for governed engineering tasks over generic git commands.
            <div style={{ color: '#737373', marginTop: 4 }}>
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
            color: '#F5F5F5',
            background: 'rgba(255, 255, 255, 0.03)',
            padding: '8px 12px',
            borderRadius: 6,
            border: '1px solid #242424',
          }}
        >
          <I.AlertCircle size={14} style={{ color: '#F97316', flexShrink: 0 }} />
          <span>
            If you already have an agent instruction file, add only the SUTRA block. Do not replace your existing instructions.
          </span>
        </div>
      </div>

      {/* Target Selector Tabs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#F5F5F5' }}>
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
                  background: selectedTarget === target.name ? 'rgba(249, 115, 22, 0.12)' : '#1C1C1C',
                  color: selectedTarget === target.name ? '#F97316' : '#A3A3A3',
                  border: selectedTarget === target.name ? '1px solid #F97316' : '1px solid #242424',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {target.name}
                {target.recommended && (
                  <span style={{ marginLeft: 4, fontSize: 10, color: '#3B82F6' }}>(Recommended)</span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div style={{ fontSize: 11, color: '#737373' }}>
          {selectedTarget === 'AGENTS.md' && 'Recommended cross-agent standard. Place as ./AGENTS.md at the root of your repository.'}
          {selectedTarget === 'CLAUDE.md' && 'Add to your existing ./CLAUDE.md file without replacing existing project instructions.'}
          {selectedTarget === 'Cursor Rules' && 'Add as a rule in .cursorrules or create .cursor/rules/sutra-governance.mdc.'}
          {selectedTarget === 'Equivalent Instruction Files' && 'Append the SUTRA block inside any workspace instruction file used by your agent harness.'}
        </div>
      </div>

      {/* Code Viewer */}
      <div
        style={{
          border: '1px solid #242424',
          borderRadius: 8,
          background: '#0B0B0B',
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
            background: '#151515',
            borderBottom: '1px solid #242424',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: 12,
                fontWeight: 600,
                color: '#F5F5F5',
              }}
            >
              {selectedTarget === 'AGENTS.md' ? 'AGENTS.md' : selectedTarget === 'CLAUDE.md' ? 'CLAUDE.md' : selectedTarget === 'Cursor Rules' ? '.cursorrules' : 'AGENTS.md'}
            </span>
            <span
              style={{
                fontSize: 11,
                color: '#737373',
                background: '#0B0B0B',
                padding: '1px 6px',
                borderRadius: 4,
                border: '1px solid #242424',
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
                background: copied ? 'rgba(16, 185, 129, 0.15)' : '#1C1C1C',
                border: copied ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid #242424',
                color: copied ? '#34D399' : '#F5F5F5',
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
            color: '#A3A3A3',
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
          color: '#737373',
          marginTop: -4,
        }}
      >
        <I.ShieldCheck size={13} style={{ color: '#3B82F6', flexShrink: 0 }} />
        <span>
          Contains zero credentials, secrets, or environment-specific URLs. Safe to commit to public or private version control.
        </span>
      </div>
    </section>
  );
}
