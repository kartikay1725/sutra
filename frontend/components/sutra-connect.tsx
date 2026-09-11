'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { I } from '../lib/icons';

export type SutraConnectionState =
  | 'not_connected'
  | 'connecting'
  | 'awaiting_authorization'
  | 'connected'
  | 'unsupported';

export interface SutraConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectionState: SutraConnectionState;
  onStateChange?: (state: SutraConnectionState) => void;
  connectedAgentName?: string | null;
  onConnectAttempt?: () => void;
}

export const CANONICAL_MCP_ENDPOINT = 'https://api.sutra.sudarshanai.com/v1/mcp';

export function getMcpEndpoint(): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    // If running in development on localhost, keep localhost:8000/v1/mcp, otherwise canonical
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return `${window.location.protocol}//${window.location.hostname}:8000/v1/mcp`;
    }
  }
  return CANONICAL_MCP_ENDPOINT;
}

export function ConnectSutraButton({
  onClick,
  state = 'not_connected',
  size = 'normal',
  style,
}: {
  onClick: () => void;
  state?: SutraConnectionState;
  size?: 'normal' | 'large';
  style?: React.CSSProperties;
}) {
  const isConnected = state === 'connected';
  const isConnecting = state === 'connecting' || state === 'awaiting_authorization';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`btn primary sutra-connect-btn ${isConnected ? 'connected' : ''}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: size === 'large' ? 10 : 8,
        padding: size === 'large' ? '12px 24px' : '8px 16px',
        fontSize: size === 'large' ? 15 : 13,
        fontWeight: 600,
        borderRadius: 10,
        background: isConnected
          ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 182, 212, 0.2))'
          : 'linear-gradient(135deg, #06b6d4, #0284c7)',
        border: isConnected
          ? '1px solid rgba(16, 185, 129, 0.5)'
          : '1px solid rgba(6, 182, 212, 0.4)',
        color: '#ffffff',
        cursor: 'pointer',
        boxShadow: isConnected
          ? '0 0 16px rgba(16, 185, 129, 0.25)'
          : '0 0 16px rgba(6, 182, 212, 0.25)',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        ...style,
      }}
      title="Connect your coding agent to SUTRA"
    >
      {isConnecting ? (
        <I.RefreshCw size={size === 'large' ? 18 : 15} className="spin" />
      ) : isConnected ? (
        <I.CheckCircle2 size={size === 'large' ? 18 : 15} style={{ color: '#34d399' }} />
      ) : (
        <I.Zap size={size === 'large' ? 18 : 15} />
      )}
      <span>{isConnected ? 'SUTRA Connected' : isConnecting ? 'Connecting...' : 'Connect SUTRA'}</span>
      {isConnected && (
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: '#10b981',
            boxShadow: '0 0 8px #10b981',
            marginLeft: 2,
          }}
        />
      )}
    </button>
  );
}

export function ConnectSutraModal({
  isOpen,
  onClose,
  connectionState,
  onStateChange,
  connectedAgentName,
  onConnectAttempt,
}: SutraConnectModalProps) {
  const [selectedClient, setSelectedClient] = useState<'cursor' | 'claude_code' | 'windsurf' | 'claude_desktop'>('cursor');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const endpoint = CANONICAL_MCP_ENDPOINT;

  const copyToClipboard = (text: string, key: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    }
  };

  const cursorSnippet = JSON.stringify(
    {
      mcpServers: {
        sutra: {
          url: endpoint,
        },
      },
    },
    null,
    2
  );

  const claudeCodeCommand = `claude mcp add --transport http sutra ${endpoint}`;

  const windsurfSnippet = JSON.stringify(
    {
      mcpServers: {
        sutra: {
          serverUrl: endpoint,
        },
      },
    },
    null,
    2
  );

  const claudeDesktopSnippet = JSON.stringify(
    {
      mcpServers: {
        sutra: {
          url: endpoint,
        },
      },
    },
    null,
    2
  );

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 7, 10, 0.78)',
        backdropFilter: 'blur(8px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
        animation: 'fadeIn 0.2s ease-out',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card"
        style={{
          width: '100%',
          maxWidth: 780,
          maxHeight: '92vh',
          overflowY: 'auto',
          backgroundColor: '#0c0f15',
          border: '1px solid rgba(6, 182, 212, 0.25)',
          borderRadius: 20,
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6), 0 0 32px rgba(6, 182, 212, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            padding: '24px 28px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.07)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'rgba(6, 182, 212, 0.15)',
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--cyan, #06b6d4)',
                }}
              >
                <I.Zap size={18} />
              </div>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f8fafc' }}>
                Connect SUTRA
              </h2>
            </div>
            <p
              style={{
                margin: '8px 0 0',
                fontSize: 13,
                color: '#94a3b8',
                lineHeight: 1.5,
              }}
            >
              Connect your local or remote coding agent (Cursor, Claude Code, Windsurf) to SUTRA governance.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 8,
              width: 32,
              height: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            aria-label="Close dialog"
          >
            <I.X size={16} />
          </button>
        </div>

        {/* Connection State Diagnostic Pill / Banner */}
        <div style={{ padding: '16px 28px 0' }}>
          <div
            style={{
              padding: '12px 18px',
              borderRadius: 12,
              background:
                connectionState === 'connected'
                  ? 'rgba(16, 185, 129, 0.08)'
                  : connectionState === 'awaiting_authorization'
                  ? 'rgba(234, 179, 8, 0.08)'
                  : connectionState === 'connecting'
                  ? 'rgba(6, 182, 212, 0.08)'
                  : 'rgba(255, 255, 255, 0.03)',
              border:
                connectionState === 'connected'
                  ? '1px solid rgba(16, 185, 129, 0.3)'
                  : connectionState === 'awaiting_authorization'
                  ? '1px solid rgba(234, 179, 8, 0.3)'
                  : connectionState === 'connecting'
                  ? '1px solid rgba(6, 182, 212, 0.3)'
                  : '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background:
                    connectionState === 'connected'
                      ? '#10b981'
                      : connectionState === 'awaiting_authorization'
                      ? '#eab308'
                      : connectionState === 'connecting'
                      ? '#06b6d4'
                      : '#94a3b8',
                  boxShadow:
                    connectionState === 'connected'
                      ? '0 0 8px #10b981'
                      : connectionState === 'awaiting_authorization'
                      ? '0 0 8px #eab308'
                      : 'none',
                }}
              />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                Status:{' '}
                {connectionState === 'not_connected' && 'Not connected'}
                {connectionState === 'connecting' && 'Detecting environment & attempting connection...'}
                {connectionState === 'awaiting_authorization' && 'Awaiting browser authorization'}
                {connectionState === 'connected' && `Connected (${connectedAgentName || 'Active Session'})`}
                {connectionState === 'unsupported' && 'Manual configuration required (Desktop agent)'}
              </span>
            </div>

            {connectionState === 'connected' ? (
              <button
                type="button"
                onClick={() => onStateChange?.('not_connected')}
                style={{
                  background: 'none',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#f87171',
                  borderRadius: 6,
                  padding: '4px 10px',
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                Disconnect
              </button>
            ) : (
              <button
                type="button"
                onClick={onConnectAttempt}
                style={{
                  background: 'rgba(6, 182, 212, 0.12)',
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                  color: '#38bdf8',
                  borderRadius: 6,
                  padding: '4px 12px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <I.RefreshCw size={12} /> Test Connection
              </button>
            )}
          </div>
        </div>

        {/* Three Connection Models Notice (Requirement 8) */}
        <div style={{ padding: '18px 28px 6px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
              gap: 10,
              fontSize: 12,
            }}
          >
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 10,
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              <div style={{ fontWeight: 600, color: '#38bdf8', marginBottom: 2 }}>
                1. Automatic Connection
              </div>
              <div style={{ color: '#94a3b8' }}>
                Zero-config OAuth discovery when initiated from compatible IDEs.
              </div>
            </div>
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 10,
                background: 'rgba(6, 182, 212, 0.04)',
                border: '1px solid rgba(6, 182, 212, 0.2)',
              }}
            >
              <div style={{ fontWeight: 600, color: '#f8fafc', marginBottom: 2 }}>
                2. Custom MCP Configuration
              </div>
              <div style={{ color: '#94a3b8' }}>
                Add the remote SUTRA MCP URL to your IDE configuration file.
              </div>
            </div>
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 10,
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              <div style={{ fontWeight: 600, color: '#a78bfa', marginBottom: 2 }}>
                3. API Integration
              </div>
              <div style={{ color: '#94a3b8' }}>
                Headless REST APIs for automated CI pipelines and scripts.
              </div>
            </div>
          </div>
        </div>

        {/* Fallback Cards Container (Requirement 5) */}
        <div
          style={{
            padding: '16px 28px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          {/* CARD 1: Custom MCP Settings */}
          <div
            className="sutra-fallback-card mcp-settings-card"
            style={{
              borderRadius: 16,
              border: '1px solid rgba(6, 182, 212, 0.25)',
              background:
                'linear-gradient(180deg, rgba(6, 182, 212, 0.05) 0%, rgba(12, 16, 24, 0.8) 100%)',
              padding: '22px 24px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 10,
                marginBottom: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  style={{
                    background: 'rgba(6, 182, 212, 0.18)',
                    color: '#38bdf8',
                    border: '1px solid rgba(6, 182, 212, 0.3)',
                    padding: '2px 8px',
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Card 1 · Recommended
                </span>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>
                  Custom MCP Settings
                </h3>
              </div>

              <span style={{ fontSize: 12, color: '#94a3b8' }}>
                Remote Streamable HTTP · OAuth 2.1
              </span>
            </div>

            <p style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 16px', lineHeight: 1.5 }}>
              For coding agents that support custom remote MCP servers (Cursor, Claude Code,
              Windsurf). Point your client to the canonical SUTRA MCP endpoint. The client will
              receive an HTTP 401 challenge, discover OAuth metadata, and launch the browser login and
              consent screen. <strong>No permanent agent token required.</strong>
            </p>

            {/* Canonical MCP Endpoint Display with 1-Click Copy */}
            <div style={{ marginBottom: 18 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#cbd5e1',
                  marginBottom: 6,
                }}
              >
                Canonical SUTRA MCP Endpoint:
              </label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 10,
                  padding: '8px 12px',
                  gap: 10,
                }}
              >
                <I.Globe2 size={16} style={{ color: '#06b6d4', flexShrink: 0 }} />
                <code
                  style={{
                    flex: 1,
                    color: '#38bdf8',
                    fontFamily: 'monospace',
                    fontSize: 13,
                    wordBreak: 'break-all',
                  }}
                >
                  {CANONICAL_MCP_ENDPOINT}
                </code>
                <button
                  type="button"
                  onClick={() => copyToClipboard(CANONICAL_MCP_ENDPOINT, 'endpoint')}
                  className="btn"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 12px',
                    fontSize: 12,
                    fontWeight: 600,
                    borderRadius: 7,
                    background:
                      copiedKey === 'endpoint'
                        ? 'rgba(16, 185, 129, 0.2)'
                        : 'rgba(255, 255, 255, 0.08)',
                    border:
                      copiedKey === 'endpoint'
                        ? '1px solid rgba(16, 185, 129, 0.4)'
                        : '1px solid rgba(255, 255, 255, 0.12)',
                    color: copiedKey === 'endpoint' ? '#34d399' : '#ffffff',
                    cursor: 'pointer',
                  }}
                >
                  {copiedKey === 'endpoint' ? <I.Check size={13} /> : <I.Copy size={13} />}
                  {copiedKey === 'endpoint' ? 'Copied' : 'Copy Endpoint'}
                </button>
              </div>
            </div>

            {/* Client Config Selector */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
                {[
                  { id: 'cursor', label: 'Cursor (~/.cursor/mcp.json)' },
                  { id: 'claude_code', label: 'Claude Code (Terminal)' },
                  { id: 'windsurf', label: 'Windsurf' },
                  { id: 'claude_desktop', label: 'Claude Desktop' },
                ].map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedClient(c.id as any)}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: selectedClient === c.id ? 600 : 400,
                      background:
                        selectedClient === c.id
                          ? 'rgba(6, 182, 212, 0.18)'
                          : 'rgba(255, 255, 255, 0.03)',
                      color: selectedClient === c.id ? '#38bdf8' : '#94a3b8',
                      border:
                        selectedClient === c.id
                          ? '1px solid rgba(6, 182, 212, 0.35)'
                          : '1px solid rgba(255, 255, 255, 0.06)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {c.label}
                  </button>
                ))}
              </div>

              {/* Snippet Display */}
              <div
                style={{
                  position: 'relative',
                  background: '#05070a',
                  borderRadius: 10,
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  padding: '14px 16px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}
                >
                  <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>
                    {selectedClient === 'cursor' && 'Add to ~/.cursor/mcp.json'}
                    {selectedClient === 'claude_code' && 'Run in Terminal'}
                    {selectedClient === 'windsurf' && 'Add to ~/.codeium/windsurf/mcp_config.json'}
                    {selectedClient === 'claude_desktop' && 'Add to claude_desktop_config.json'}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      const snippet =
                        selectedClient === 'cursor'
                          ? cursorSnippet
                          : selectedClient === 'claude_code'
                          ? claudeCodeCommand
                          : selectedClient === 'windsurf'
                          ? windsurfSnippet
                          : claudeDesktopSnippet;
                      copyToClipboard(snippet, 'snippet');
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: copiedKey === 'snippet' ? '#34d399' : '#38bdf8',
                      cursor: 'pointer',
                      fontSize: 12,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: 0,
                    }}
                  >
                    {copiedKey === 'snippet' ? <I.Check size={12} /> : <I.Copy size={12} />}
                    {copiedKey === 'snippet' ? 'Copied' : 'Copy'}
                  </button>
                </div>

                <pre
                  style={{
                    margin: 0,
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: '#e2e8f0',
                    lineHeight: 1.5,
                    overflowX: 'auto',
                  }}
                >
                  {selectedClient === 'cursor' && cursorSnippet}
                  {selectedClient === 'claude_code' && claudeCodeCommand}
                  {selectedClient === 'windsurf' && windsurfSnippet}
                  {selectedClient === 'claude_desktop' && claudeDesktopSnippet}
                </pre>
              </div>
            </div>

            <div
              style={{
                fontSize: 12,
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginTop: 6,
              }}
            >
              <I.ShieldCheck size={14} style={{ color: '#10b981' }} />
              <span>
                Tokens are minted dynamically via PKCE OAuth. Never commit or share permanent credentials.
              </span>
            </div>
          </div>

          {/* CARD 2: API Integration */}
          <div
            className="sutra-fallback-card api-integration-card"
            style={{
              borderRadius: 16,
              border: '1px solid rgba(255, 255, 255, 0.1)',
              background:
                'linear-gradient(180deg, rgba(255, 255, 255, 0.02) 0%, rgba(12, 15, 22, 0.8) 100%)',
              padding: '22px 24px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 10,
                marginBottom: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  style={{
                    background: 'rgba(168, 85, 247, 0.15)',
                    color: '#c084fc',
                    border: '1px solid rgba(168, 85, 247, 0.3)',
                    padding: '2px 8px',
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Card 2 · Fallback
                </span>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>
                  API Integration
                </h3>
              </div>

              <span style={{ fontSize: 12, color: '#94a3b8' }}>REST / CI Pipelines</span>
            </div>

            <p style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 14px', lineHeight: 1.5 }}>
              Fallback for automated pipelines, CI/CD runners, and custom scripts that cannot use the
              remote MCP OAuth flow. SUTRA exposes secure REST APIs for governance, change evaluation,
              and provenance verification.
            </p>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 12,
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '12px 16px',
                borderRadius: 10,
                border: '1px solid rgba(255, 255, 255, 0.05)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <I.Book size={18} style={{ color: '#a78bfa' }} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>
                    SUTRA Engineering API Reference
                  </div>
                  <div style={{ fontSize: 12, color: '#94a3b8' }}>
                    Explore endpoints, webhook verification, and human merge governance.
                  </div>
                </div>
              </div>

              <Link
                href="/docs"
                className="btn"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  borderRadius: 8,
                  background: 'rgba(168, 85, 247, 0.15)',
                  border: '1px solid rgba(168, 85, 247, 0.35)',
                  color: '#e9d5ff',
                  textDecoration: 'none',
                }}
              >
                <span>Read Documentation</span>
                <I.ExternalLink size={13} />
              </Link>
            </div>

            <div
              style={{
                fontSize: 12,
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginTop: 12,
              }}
            >
              <I.Lock size={14} style={{ color: '#eab308' }} />
              <span>
                Zero credentials exposed in browser. Server-side secrets must be provisioned by organization administrators.
              </span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '16px 28px',
            borderTop: '1px solid rgba(255, 255, 255, 0.07)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            background: 'rgba(0, 0, 0, 0.2)',
          }}
        >
          <a
            href="/oauth/authorize?client_id=sutra-mcp-client&redirect_uri=https://api.sutra.sudarshanai.com/oauth/callback&response_type=code&scope=sutra:agent&code_challenge=E9Melhoa2OwvFrGMTJguCH5rtx64LxU408W32BgV16g&code_challenge_method=S256"
            target="_blank"
            rel="noreferrer"
            onClick={() => onStateChange?.('awaiting_authorization')}
            style={{
              fontSize: 13,
              color: '#38bdf8',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              textDecoration: 'none',
            }}
          >
            <I.ExternalLink size={14} />
            <span>Test Browser OAuth Authorization Flow</span>
          </a>

          <button
            type="button"
            onClick={onClose}
            className="btn"
            style={{
              padding: '8px 20px',
              fontSize: 13,
              fontWeight: 600,
              borderRadius: 8,
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#ffffff',
              cursor: 'pointer',
            }}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
