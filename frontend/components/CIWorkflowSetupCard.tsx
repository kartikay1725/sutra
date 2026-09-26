'use client';

import React, { useState } from 'react';
import * as LucideIcons from 'lucide-react';

export interface CIWorkflowSetupCardProps {
  repoName?: string;
  repoOwner?: string;
  defaultExpanded?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const TEMPLATES = {
  python: {
    label: 'Python / FastAPI',
    icon: LucideIcons.FileCode,
    filename: '.github/workflows/ci.yml',
    content: `name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    name: Test & Verify
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi
          pip install pytest pytest-cov httpx || true

      - name: Run Tests
        run: pytest
`,
  },
  node: {
    label: 'Node.js / Next.js',
    icon: LucideIcons.FileCode,
    filename: '.github/workflows/ci.yml',
    content: `name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    name: Test & Verify
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci || npm install

      - name: Run Tests & Build
        run: |
          npm test
          npm run build --if-present
`,
  },
  generic: {
    label: 'Generic / Shell',
    icon: LucideIcons.Terminal,
    filename: '.github/workflows/ci.yml',
    content: `name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  verify:
    name: Repository Verification
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Run Automated Checks
        run: |
          echo "Running repository verification checks..."
          # Insert your test or build commands here
`,
  },
};

type TemplateKey = keyof typeof TEMPLATES;

export function CIWorkflowSetupCard({
  repoName,
  repoOwner,
  defaultExpanded = false,
  className = '',
  style,
}: CIWorkflowSetupCardProps) {
  const [activeTab, setActiveTab] = useState<TemplateKey>('python');
  const [expanded, setExpanded] = useState<boolean>(defaultExpanded);
  const [copied, setCopied] = useState<boolean>(false);
  const [copiedPath, setCopiedPath] = useState<boolean>(false);

  const template = TEMPLATES[activeTab];

  const handleCopyCode = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(template.content);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy CI workflow:', err);
    }
  };

  const handleCopyPath = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(template.filename);
      }
      setCopiedPath(true);
      setTimeout(() => setCopiedPath(false), 2000);
    } catch (err) {
      console.error('Failed to copy filename path:', err);
    }
  };

  const actionsUrl = repoOwner && repoName
    ? `https://github.com/${repoOwner}/${repoName}/actions`
    : null;

  return (
    <div
      className={`ci-workflow-setup-card ${className}`}
      style={{
        borderRadius: 12,
        border: '1px solid var(--border-default, #242424)',
        background: 'var(--card, #151515)',
        padding: '24px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        ...style,
      }}
    >
      {/* Top Banner Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', flex: 1, minWidth: 280 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 10,
              background: 'var(--accent-subtle, rgba(249, 115, 22, 0.12))',
              border: '1px solid rgba(249, 115, 22, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent, #F97316)',
              flexShrink: 0,
            }}
          >
            <LucideIcons.Workflow size={20} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <h3
                style={{
                  margin: 0,
                  fontSize: 16,
                  fontWeight: 700,
                  color: 'var(--text-bright, #F5F5F5)',
                  letterSpacing: '-0.01em',
                }}
              >
                GitHub Actions Native CI & Verification
              </h3>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: 4,
                  background: 'rgba(16, 185, 129, 0.12)',
                  color: '#10b981',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  letterSpacing: '0.02em',
                }}
              >
                PR Merge Not Blocked
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: 4,
                  background: 'var(--link-subtle, rgba(59, 130, 246, 0.12))',
                  color: 'var(--link, #3B82F6)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                }}
              >
                GitHub Cloud Runners
              </span>
            </div>

            <p
              style={{
                margin: '6px 0 0 0',
                fontSize: 13,
                color: 'var(--muted, #8A8A8A)',
                lineHeight: 1.55,
                maxWidth: 680,
              }}
            >
              Automated checks execute safely on GitHub Actions runners. If no CI workflow file exists in your codebase, SUTRA indicates that checks cannot be run, and <strong style={{ color: 'var(--text-bright, #F5F5F5)' }}>never blocks Pull Requests from being merged</strong>.
            </p>
          </div>
        </div>

        {/* Quick action buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {actionsUrl && (
            <a
              href={actionsUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 13px',
                borderRadius: 7,
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--text-bright, #F5F5F5)',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid var(--border-default, #242424)',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <LucideIcons.ExternalLink size={13} style={{ color: 'var(--link, #3B82F6)' }} />
              Open GitHub Actions
            </a>
          )}

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 13px',
              borderRadius: 7,
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--text-bright, #F5F5F5)',
              background: 'var(--surface-2, #181818)',
              border: '1px solid var(--border-default, #2A2A2A)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <LucideIcons.Code2 size={13} style={{ color: 'var(--accent, #F97316)' }} />
            {expanded ? 'Hide ci.yml Template' : 'View ci.yml Template'}
            <LucideIcons.ChevronDown
              size={13}
              style={{
                transform: expanded ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.2s ease',
              }}
            />
          </button>
        </div>
      </div>

      {/* Zero-Blocker & CI Policy Info Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 12,
          paddingTop: 4,
        }}
      >
        <div
          style={{
            background: 'var(--surface-2, #141414)',
            border: '1px solid var(--border-default, #242424)',
            borderRadius: 10,
            padding: '14px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#10b981', fontSize: 13, fontWeight: 600 }}>
            <LucideIcons.CheckCircle2 size={15} />
            Zero-Blocker Governance
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: 'var(--muted, #8A8A8A)', lineHeight: 1.5 }}>
            Repositories without a <code style={{ color: 'var(--text-bright, #F5F5F5)', background: 'rgba(255,255,255,0.06)', padding: '1px 5px', borderRadius: 4 }}>ci.yml</code> file automatically waive automated CI checks; PR merges are never blocked.
          </div>
        </div>

        <div
          style={{
            background: 'var(--surface-2, #141414)',
            border: '1px solid var(--border-default, #242424)',
            borderRadius: 10,
            padding: '14px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--link, #3B82F6)', fontSize: 13, fontWeight: 600 }}>
            <LucideIcons.ShieldCheck size={15} />
            Isolated Cloud Runners
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: 'var(--muted, #8A8A8A)', lineHeight: 1.5 }}>
            CI runs directly in GitHub Actions environments, eliminating untrusted host container execution or docker dependency issues.
          </div>
        </div>

        <div
          style={{
            background: 'var(--surface-2, #141414)',
            border: '1px solid var(--border-default, #242424)',
            borderRadius: 10,
            padding: '14px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent, #F97316)', fontSize: 13, fontWeight: 600 }}>
            <LucideIcons.GitPullRequest size={15} />
            Real-Time SUTRA Sync
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: 'var(--muted, #8A8A8A)', lineHeight: 1.5 }}>
            When a PR is opened, GitHub Actions dispatches checks and SUTRA syncs conclusions, failure reasons, and direct links instantly.
          </div>
        </div>
      </div>

      {/* Expandable Template Viewer */}
      {expanded && (
        <div
          style={{
            marginTop: 4,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            borderTop: '1px solid var(--border-default, #242424)',
            paddingTop: 16,
          }}
        >
          {/* Header row with Tabs and Copy Button */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            {/* Template Stack Tabs */}
            <div
              style={{
                display: 'inline-flex',
                background: 'var(--surface-2, #141414)',
                padding: 3,
                borderRadius: 8,
                border: '1px solid var(--border-default, #242424)',
                gap: 4,
              }}
            >
              {(Object.keys(TEMPLATES) as TemplateKey[]).map((key) => {
                const item = TEMPLATES[key];
                const isActive = activeTab === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '5px 11px',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? 'var(--accent, #F97316)' : 'var(--muted, #8A8A8A)',
                      background: isActive ? 'var(--accent-subtle, rgba(249, 115, 22, 0.12))' : 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <item.icon size={13} />
                    {item.label}
                  </button>
                );
              })}
            </div>

            {/* Target Path & Copy Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                onClick={handleCopyPath}
                title="Click to copy path"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 10px',
                  borderRadius: 6,
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid var(--border-default, #242424)',
                  color: 'var(--muted, #8A8A8A)',
                  fontSize: 11,
                  fontFamily: 'monospace',
                  cursor: 'pointer',
                }}
              >
                <LucideIcons.FolderPlus size={12} />
                {template.filename}
                {copiedPath ? (
                  <span style={{ color: '#10b981', fontSize: 10, fontWeight: 600 }}>Copied!</span>
                ) : (
                  <LucideIcons.Copy size={11} />
                )}
              </button>

              <button
                type="button"
                onClick={handleCopyCode}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 14px',
                  borderRadius: 7,
                  fontSize: 12,
                  fontWeight: 600,
                  color: copied ? '#ffffff' : '#0B0B0B',
                  background: copied ? '#10b981' : 'var(--accent, #F97316)',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 2px 10px rgba(249, 115, 22, 0.25)',
                  transition: 'all 0.15s ease',
                }}
              >
                {copied ? <LucideIcons.Check size={13} /> : <LucideIcons.Copy size={13} />}
                {copied ? 'Copied Workflow!' : 'Copy ci.yml'}
              </button>
            </div>
          </div>

          {/* Workflow Code Container */}
          <div
            style={{
              position: 'relative',
              borderRadius: 8,
              background: '#070707',
              border: '1px solid var(--border-default, #242424)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 14px',
                background: 'rgba(255, 255, 255, 0.02)',
                borderBottom: '1px solid var(--border-default, #202020)',
                fontSize: 11,
                color: 'var(--muted, #8A8A8A)',
                fontFamily: 'monospace',
              }}
            >
              <span>{template.filename}</span>
              <span>YAML Workflow</span>
            </div>

            <pre
              style={{
                margin: 0,
                padding: '16px 18px',
                fontSize: 12,
                lineHeight: 1.6,
                color: '#cbd5e1',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                overflowX: 'auto',
                whiteSpace: 'pre',
              }}
            >
              {template.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
