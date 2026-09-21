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
  { border: string; bg: string; iconColor: string; defaultTitle: string; icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }> }
> = {
  note: {
    border: 'rgba(59, 130, 246, 0.25)',
    bg: 'rgba(59, 130, 246, 0.05)',
    iconColor: '#60A5FA',
    defaultTitle: 'Note',
    icon: Info,
  },
  important: {
    border: 'rgba(59, 130, 246, 0.25)',
    bg: 'rgba(59, 130, 246, 0.05)',
    iconColor: '#60A5FA',
    defaultTitle: 'Important',
    icon: Sparkles,
  },
  warning: {
    border: 'rgba(249, 115, 22, 0.32)',
    bg: 'rgba(249, 115, 22, 0.06)',
    iconColor: '#F97316',
    defaultTitle: 'Warning',
    icon: AlertTriangle,
  },
  security: {
    border: 'rgba(249, 115, 22, 0.32)',
    bg: 'rgba(249, 115, 22, 0.06)',
    iconColor: '#F97316',
    defaultTitle: 'Security Boundary',
    icon: ShieldAlert,
  },
  example: {
    border: 'rgba(59, 130, 246, 0.25)',
    bg: 'rgba(59, 130, 246, 0.05)',
    iconColor: '#60A5FA',
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
        fontSize: 13,
        lineHeight: 1.6,
        color: '#D4D4D8',
        ...style,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontWeight: 600,
          color: config.iconColor,
          marginBottom: 6,
          fontSize: 12,
          letterSpacing: '0.02em',
          textTransform: 'uppercase',
        }}
      >
        <Icon size={14} style={{ flexShrink: 0 }} />
        <span>{displayTitle}</span>
      </div>
      <div style={{ color: '#A1A1AA' }}>{children}</div>
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
    color: '#FAFAFA',
    fontWeight: 700,
    letterSpacing: '-0.02em',
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    scrollMarginTop: 80,
    marginTop: level === 2 ? 32 : 24,
    marginBottom: 12,
    fontSize: level === 2 ? 20 : 16,
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
          color: '#F97316',
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
        border: '1px solid #222226',
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
  GET: { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.35)', text: '#60A5FA' },
  POST: { bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.35)', text: '#F97316' },
  PUT: { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.35)', text: '#58A6FF' },
  PATCH: { bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.35)', text: '#FB923C' },
  DELETE: { bg: 'rgba(255, 255, 255, 0.06)', border: 'rgba(255, 255, 255, 0.25)', text: '#F0F6FC' },
  'STREAMABLE HTTP': { bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.35)', text: '#FB923C' },
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
        background: '#111418',
        border: '1px solid #202632',
        borderRadius: 10,
        overflow: 'hidden',
        margin: '14px 0',
        transition: 'border-color 0.15s ease',
      }}
      className="hover:border-[#30363D]"
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
          background: isOpen ? '#141820' : '#111418',
          borderBottom: isOpen ? '1px solid #202632' : 'none',
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
              color: '#F0F6FC',
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
              color: copied ? '#F97316' : '#8B949E',
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
          <span style={{ fontSize: 12, color: '#8B949E', display: 'none', minWidth: 0 }} className="md:inline">
            {summary}
          </span>

          {/* Auth requirement tag */}
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              padding: '2px 8px',
              borderRadius: 4,
              background: '#161B22',
              border: '1px solid #30363D',
              color: '#C9D1D9',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              whiteSpace: 'nowrap',
            }}
          >
            <Lock size={10} style={{ color: '#8B949E' }} />
            <span>{auth}</span>
          </span>

          {hasDetails && (
            <span style={{ color: '#8B949E', display: 'flex', alignItems: 'center' }}>
              {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </span>
          )}
        </div>
      </div>

      {/* Expanded Details Body */}
      {isOpen && (
        <div style={{ padding: '16px 18px', background: '#0D1117' }}>
          {description && (
            <p style={{ fontSize: 13, color: '#C9D1D9', lineHeight: 1.6, margin: '0 0 14px 0' }}>
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
                background: 'rgba(249, 115, 22, 0.08)',
                border: '1px solid rgba(249, 115, 22, 0.25)',
                borderRadius: 6,
                fontSize: 12,
                color: '#F97316',
                marginBottom: 16,
              }}
            >
              <ShieldCheck size={14} style={{ flexShrink: 0 }} />
              <span><strong>Rule:</strong> {rule}</span>
            </div>
          )}

          {/* Tab Navigation for Parameters, Request & Response */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, borderBottom: '1px solid #21262D', marginBottom: 14 }}>
            {parameters && parameters.length > 0 && (
              <button
                type="button"
                onClick={() => setActiveTab('params')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'params' ? '2px solid #F97316' : '2px solid transparent',
                  padding: '6px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: activeTab === 'params' ? '#F0F6FC' : '#8B949E',
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
                  borderBottom: activeTab === 'request' ? '2px solid #F97316' : '2px solid transparent',
                  padding: '6px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: activeTab === 'request' ? '#F0F6FC' : '#8B949E',
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
                  borderBottom: activeTab === 'response' ? '2px solid #F97316' : '2px solid transparent',
                  padding: '6px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: activeTab === 'response' ? '#F0F6FC' : '#8B949E',
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
                  <tr style={{ borderBottom: '1px solid #21262D', color: '#8B949E', textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.05em' }}>
                    <th style={{ padding: '6px 10px' }}>Name</th>
                    <th style={{ padding: '6px 10px' }}>Type</th>
                    <th style={{ padding: '6px 10px' }}>In</th>
                    <th style={{ padding: '6px 10px' }}>Required</th>
                    <th style={{ padding: '6px 10px' }}>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {parameters.map((p) => (
                    <tr key={p.name} style={{ borderBottom: '1px solid #161B22' }}>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, color: '#58A6FF' }}>
                        {p.name}
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono, monospace)', color: '#8B949E', fontSize: 11 }}>
                        {p.type}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: '#161B22', color: '#C9D1D9', textTransform: 'uppercase' }}>
                          {p.in}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        {p.required ? (
                          <span style={{ fontSize: 10, color: '#F97316', fontWeight: 700 }}>yes</span>
                        ) : (
                          <span style={{ fontSize: 10, color: '#8B949E' }}>optional</span>
                        )}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#C9D1D9', lineHeight: 1.4 }}>
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

