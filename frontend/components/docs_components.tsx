'use client';

import React, { useState } from 'react';
import {
  Check,
  Copy,
  Info,
  AlertTriangle,
  ShieldAlert,
  HelpCircle,
  Hash,
  Sparkles,
  Lock,
  Key,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
} from 'lucide-react';

/* ==========================================================================
   1. Semantic Docs Callout Component
   ========================================================================== */
export type CalloutType = 'note' | 'important' | 'warning' | 'security' | 'example';

interface DocsCalloutProps {
  type?: CalloutType;
  title?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

const CALLOUT_CONFIG: Record<
  CalloutType,
  { border: string; bg: string; iconColor: string; textColor: string; defaultTitle: string; icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }> }
> = {
  note: {
    border: '#BFDBFE',
    bg: '#EFF6FF',
    iconColor: '#2563EB',
    textColor: '#1E40AF',
    defaultTitle: 'Note',
    icon: Info,
  },
  important: {
    border: '#BBF7D0',
    bg: '#F0FDF4',
    iconColor: '#16A34A',
    textColor: '#166534',
    defaultTitle: 'Important',
    icon: Sparkles,
  },
  warning: {
    border: '#FED7AA',
    bg: '#FFF7ED',
    iconColor: '#EA580C',
    textColor: '#9A3412',
    defaultTitle: 'Warning',
    icon: AlertTriangle,
  },
  security: {
    border: '#FECDD3',
    bg: '#FFF1F2',
    iconColor: '#E11D48',
    textColor: '#9F1239',
    defaultTitle: 'Security Boundary',
    icon: ShieldAlert,
  },
  example: {
    border: '#E2E8F0',
    bg: '#F8FAFC',
    iconColor: '#475569',
    textColor: '#334155',
    defaultTitle: 'Example',
    icon: HelpCircle,
  },
};

export function DocsCallout({
  type = 'note',
  title,
  children,
  style,
}: DocsCalloutProps) {
  const config = CALLOUT_CONFIG[type];
  const Icon = config.icon;
  const displayTitle = title || config.defaultTitle;

  return (
    <div
      style={{
        border: `1px solid ${config.border}`,
        background: config.bg,
        borderRadius: 8,
        padding: '14px 16px',
        margin: '16px 0',
        fontSize: 13.5,
        lineHeight: 1.65,
        color: config.textColor,
        ...style,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontWeight: 700,
          color: config.iconColor,
          marginBottom: 6,
          fontSize: 12,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        <Icon size={14} style={{ flexShrink: 0 }} />
        <span>{displayTitle}</span>
      </div>
      <div style={{ color: config.textColor }}>{children}</div>
    </div>
  );
}

/* ==========================================================================
   2. Clean Docs Code Block with 1-Click Copy
   ========================================================================== */
interface DocsCodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  style?: React.CSSProperties;
}

export function DocsCodeBlock({
  code,
  language = 'bash',
  filename,
  style,
}: DocsCodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (err) {
      console.error('Failed to copy code snippet:', err);
    }
  };

  return (
    <div
      style={{
        border: '1px solid #222226',
        borderRadius: 8,
        background: '#0D0D10',
        overflow: 'hidden',
        margin: '16px 0',
        ...style,
      }}
    >
      {/* Code Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          borderBottom: '1px solid #1C1C20',
          background: '#121216',
          fontSize: 11,
          fontFamily: 'JetBrains Mono, monospace',
        }}
      >
        <span style={{ color: filename ? '#D4D4D8' : '#71717A', fontWeight: filename ? 600 : 400 }}>
          {filename || language}
        </span>
        <button
          onClick={handleCopy}
          type="button"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            padding: '3px 8px',
            fontSize: 11,
            color: copied ? '#F97316' : '#A1A1AA',
            background: copied ? 'rgba(249, 115, 22, 0.12)' : '#1A1A20',
            border: `1px solid ${copied ? 'rgba(249, 115, 22, 0.3)' : '#27272E'}`,
            borderRadius: 4,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          title="Copy code to clipboard"
          aria-label="Copy code to clipboard"
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>

      {/* Code Content */}
      <pre
        style={{
          margin: 0,
          padding: '14px 16px',
          fontFamily: 'JetBrains Mono, Menlo, monospace',
          fontSize: 12.5,
          lineHeight: 1.6,
          color: '#E4E4E7',
          overflowX: 'auto',
          maxWidth: '100%',
          tabSize: 2,
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

/* ==========================================================================
   3. Deep-Linkable Section Heading Component
   ========================================================================== */
interface DocsHeadingProps {
  id: string;
  level?: 2 | 3;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function DocsHeading({
  id,
  level = 2,
  children,
  style,
}: DocsHeadingProps) {
  const [hovered, setHovered] = useState(false);

  const headingStyle: React.CSSProperties = {
    color: '#0F172A',
    fontWeight: level === 2 ? 800 : 700,
    letterSpacing: '-0.025em',
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    scrollMarginTop: 80,
    marginTop: level === 2 ? 32 : 24,
    marginBottom: 12,
    fontSize: level === 2 ? 21 : 16.5,
    lineHeight: 1.3,
    ...style,
  };

  return (
    <div
      id={id}
      style={headingStyle}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span>{children}</span>
      <a
        href={`#${id}`}
        aria-label={`Link to ${children}`}
        style={{
          opacity: hovered ? 1 : 0,
          transition: 'opacity 0.15s ease',
          color: '#EA580C',
          display: 'inline-flex',
          alignItems: 'center',
          textDecoration: 'none',
        }}
      >
        <Hash size={level === 2 ? 16 : 14} />
      </a>
    </div>
  );
}

/* ==========================================================================
   4. Local Horizontal Overflow Table Wrapper
   ========================================================================== */
interface DocsTableProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function DocsTable({ children, style }: DocsTableProps) {
  return (
    <div
      style={{
        overflowX: 'auto',
        maxWidth: '100%',
        margin: '16px 0',
        borderRadius: 8,
        border: '1px solid #E2E8F0',
        background: '#FFFFFF',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/* ==========================================================================
   5. Interactive ApiEndpointCard Component
   ========================================================================== */
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'STREAMABLE HTTP';

export interface ApiParam {
  name: string;
  type: string;
  in: 'path' | 'query' | 'header' | 'body';
  required?: boolean;
  description: string;
}

export interface ApiEndpointCardProps {
  method: HttpMethod;
  path: string;
  summary: string;
  auth: string;
  description?: string;
  parameters?: ApiParam[];
  requestPayload?: string;
  requestLang?: string;
  responsePayload?: string;
  responseStatus?: string;
  rule?: string;
  initiallyOpen?: boolean;
}

const METHOD_THEMES: Record<HttpMethod, { bg: string; border: string; text: string }> = {
  GET: { bg: '#EFF6FF', border: '#BFDBFE', text: '#1D4ED8' },
  POST: { bg: '#FFF7ED', border: '#FED7AA', text: '#C2410C' },
  PUT: { bg: '#F0FDF4', border: '#BBF7D0', text: '#15803D' },
  PATCH: { bg: '#FAF5FF', border: '#E9D5FF', text: '#7E22CE' },
  DELETE: { bg: '#FEF2F2', border: '#FECACA', text: '#B91C1C' },
  'STREAMABLE HTTP': { bg: '#FFF7ED', border: '#FED7AA', text: '#C2410C' },
};

export function ApiEndpointCard({
  method,
  path,
  summary,
  auth,
  description,
  parameters,
  requestPayload,
  requestLang = 'json',
  responsePayload,
  responseStatus = '200 OK',
  rule,
  initiallyOpen = false,
}: ApiEndpointCardProps) {
  const [isOpen, setIsOpen] = useState(initiallyOpen);
  const [activeTab, setActiveTab] = useState<'params' | 'request' | 'response'>(
    parameters && parameters.length > 0 ? 'params' : requestPayload ? 'request' : 'response'
  );
  const [copied, setCopied] = useState(false);

  const theme = METHOD_THEMES[method] || METHOD_THEMES.GET;

  const handleCopyPath = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(path);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (err) {
      console.error('Failed to copy path:', err);
    }
  };

  const hasDetails = Boolean(
    (parameters && parameters.length > 0) || requestPayload || responsePayload || description || rule
  );

  return (
    <div
      style={{
        background: '#FFFFFF',
        border: '1px solid #E2E8F0',
        borderRadius: 10,
        overflow: 'hidden',
        margin: '14px 0',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
        transition: 'border-color 0.15s ease',
      }}
    >
      {/* Endpoint Header Bar */}
      <div
        onClick={() => hasDetails && setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          cursor: hasDetails ? 'pointer' : 'default',
          background: isOpen ? '#F8FAFC' : '#FFFFFF',
          borderBottom: isOpen ? '1px solid #E2E8F0' : 'none',
          userSelect: 'none',
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 260 }}>
          {/* Method Badge */}
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              fontFamily: 'var(--font-mono, monospace)',
              padding: '2px 7px',
              borderRadius: 4,
              background: theme.bg,
              border: `1px solid ${theme.border}`,
              color: theme.text,
              letterSpacing: '0.04em',
              flexShrink: 0,
            }}
          >
            {method}
          </span>

          {/* Path */}
          <span
            style={{
              fontSize: 13,
              fontFamily: 'var(--font-mono, monospace)',
              fontWeight: 600,
              color: '#0F172A',
              wordBreak: 'break-all',
            }}
          >
            {path}
          </span>

          {/* Copy path icon button */}
          <button
            onClick={handleCopyPath}
            type="button"
            style={{
              background: 'none',
              border: 'none',
              color: copied ? '#EA580C' : '#64748B',
              cursor: 'pointer',
              padding: 2,
              display: 'inline-flex',
              alignItems: 'center',
              flexShrink: 0,
            }}
            title="Copy endpoint path"
            aria-label="Copy endpoint path"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>

        {/* Right side summary & auth */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: '#64748B', display: 'none', minWidth: 0 }} className="md:inline">
            {summary}
          </span>

          {/* Auth requirement tag */}
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              padding: '2px 8px',
              borderRadius: 4,
              background: '#F1F5F9',
              border: '1px solid #E2E8F0',
              color: '#475569',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              whiteSpace: 'nowrap',
            }}
          >
            <Lock size={10} style={{ color: '#64748B' }} />
            <span>{auth}</span>
          </span>

          {hasDetails && (
            <span style={{ color: '#64748B', display: 'flex', alignItems: 'center' }}>
              {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </span>
          )}
        </div>
      </div>

      {/* Expanded Details Body */}
      {isOpen && (
        <div style={{ padding: '16px 18px', background: '#FAFAFA' }}>
          {description && (
            <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.6, margin: '0 0 14px 0' }}>
              {description}
            </p>
          )}

          {rule && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 12px',
                background: 'rgba(234, 88, 12, 0.08)',
                border: '1px solid rgba(234, 88, 12, 0.25)',
                borderRadius: 6,
                fontSize: 12,
                color: '#EA580C',
                marginBottom: 16,
              }}
            >
              <ShieldCheck size={14} style={{ flexShrink: 0 }} />
              <span><strong>Rule:</strong> {rule}</span>
            </div>
          )}

          {/* Tab Navigation for Parameters, Request & Response */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, borderBottom: '1px solid #E2E8F0', marginBottom: 14 }}>
            {parameters && parameters.length > 0 && (
              <button
                type="button"
                onClick={() => setActiveTab('params')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'params' ? '2px solid #EA580C' : '2px solid transparent',
                  padding: '6px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: activeTab === 'params' ? '#0F172A' : '#64748B',
                  cursor: 'pointer',
                  marginBottom: -1,
                }}
              >
                Parameters ({parameters.length})
              </button>
            )}

            {requestPayload && (
              <button
                type="button"
                onClick={() => setActiveTab('request')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'request' ? '2px solid #EA580C' : '2px solid transparent',
                  padding: '6px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: activeTab === 'request' ? '#0F172A' : '#64748B',
                  cursor: 'pointer',
                  marginBottom: -1,
                }}
              >
                Request Body
              </button>
            )}

            {responsePayload && (
              <button
                type="button"
                onClick={() => setActiveTab('response')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'response' ? '2px solid #EA580C' : '2px solid transparent',
                  padding: '6px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: activeTab === 'response' ? '#0F172A' : '#64748B',
                  cursor: 'pointer',
                  marginBottom: -1,
                }}
              >
                Response ({responseStatus})
              </button>
            )}
          </div>

          {/* Tab Content: Parameters */}
          {activeTab === 'params' && parameters && parameters.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #E2E8F0', color: '#64748B', textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.05em' }}>
                    <th style={{ padding: '6px 10px' }}>Name</th>
                    <th style={{ padding: '6px 10px' }}>Type</th>
                    <th style={{ padding: '6px 10px' }}>In</th>
                    <th style={{ padding: '6px 10px' }}>Required</th>
                    <th style={{ padding: '6px 10px' }}>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {parameters.map((p) => (
                    <tr key={p.name} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, color: '#0284C7' }}>
                        {p.name}
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono, monospace)', color: '#64748B', fontSize: 11 }}>
                        {p.type}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: '#F1F5F9', color: '#475569', textTransform: 'uppercase' }}>
                          {p.in}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        {p.required ? (
                          <span style={{ fontSize: 10, color: '#EA580C', fontWeight: 700 }}>yes</span>
                        ) : (
                          <span style={{ fontSize: 10, color: '#94A3B8' }}>optional</span>
                        )}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#334155', lineHeight: 1.4 }}>
                        {p.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab Content: Request Payload */}
          {activeTab === 'request' && requestPayload && (
            <DocsCodeBlock
              code={requestPayload}
              language={requestLang}
              filename="Request Payload"
              style={{ margin: 0 }}
            />
          )}

          {/* Tab Content: Response Payload */}
          {activeTab === 'response' && responsePayload && (
            <DocsCodeBlock
              code={responsePayload}
              language="json"
              filename={`Response (${responseStatus})`}
              style={{ margin: 0 }}
            />
          )}
        </div>
      )}
    </div>
  );
}

