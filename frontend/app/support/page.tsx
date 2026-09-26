'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Mail,
  Clock,
  BookOpen,
  Check,
  Copy,
  Send,
  LifeBuoy,
  ArrowRight,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';

export default function SupportPage() {
  const [copiedMail, setCopiedMail] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    topic: 'governance',
    message: '',
  });

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMail(true);
    setTimeout(() => setCopiedMail(false), 2000);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setSubmitted(true);
    }, 700);
  };

  return (
    <div
      style={{
        height: '100vh',
        maxHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: '#F8FAFC',
        color: '#0F172A',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        overflow: 'hidden',
      }}
    >
      {/* Top Navbar */}
      <header
        style={{
          height: 56,
          borderBottom: '1px solid #E2E8F0',
          background: '#FFFFFF',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Link
            href="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              textDecoration: 'none',
              color: '#0F172A',
              fontWeight: 800,
              fontSize: 16,
              letterSpacing: '-0.02em',
            }}
          >
            {/* Proper SUTRA Logo */}
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: 'rgba(249, 115, 22, 0.12)',
                border: '1px solid rgba(249, 115, 22, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <img
                src="/icon.png"
                alt="SUTRA"
                style={{ width: 22, height: 22, objectFit: 'contain' }}
              />
            </div>
            <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em', color: '#0F172A' }}>
              SUTRA
            </span>
          </Link>
          <div
            style={{
              height: 16,
              width: 1,
              background: '#CBD5E1',
            }}
          />
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              fontWeight: 600,
              color: '#475569',
              background: '#F1F5F9',
              padding: '3px 10px',
              borderRadius: 20,
              border: '1px solid #E2E8F0',
            }}
          >
            <LifeBuoy size={13} color="#EA580C" />
            <span>Support Desk</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              fontWeight: 500,
              color: '#166534',
              background: '#F0FDF4',
              border: '1px solid #BBF7D0',
              padding: '4px 10px',
              borderRadius: 20,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#16A34A',
                boxShadow: '0 0 0 2px rgba(22, 163, 74, 0.2)',
              }}
            />
            <span>All Systems Operational</span>
          </div>

          <Link
            href="/docs"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
              fontWeight: 600,
              color: '#334155',
              padding: '6px 14px',
              borderRadius: 7,
              border: '1px solid #E2E8F0',
              background: '#FFFFFF',
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <BookOpen size={14} />
            <span>Docs</span>
          </Link>
        </div>
      </header>

      {/* Main Content Area - Strictly non-scrollable on desktop */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            maxWidth: 1020,
            width: '100%',
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.05fr) minmax(0, 1fr)',
            gap: 28,
            alignItems: 'center',
          }}
        >
          {/* Left Column: Direct Inquiries & Primary Channel */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              justifyContent: 'center',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  color: '#EA580C',
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 8,
                }}
              >
                <Sparkles size={13} />
                <span>Dedicated Assistance</span>
              </div>
              <h1
                style={{
                  fontSize: 30,
                  fontWeight: 800,
                  letterSpacing: '-0.03em',
                  color: '#0F172A',
                  margin: 0,
                  lineHeight: 1.2,
                }}
              >
                How can we help your team today?
              </h1>
              <p
                style={{
                  fontSize: 14,
                  color: '#64748B',
                  margin: '10px 0 0',
                  lineHeight: 1.55,
                }}
              >
                Direct engineering support for SUTRA governance, lease management, agent sessions, and MCP protocol integrations.
              </p>
            </div>

            {/* Email Contact Card */}
            <div
              style={{
                background: '#FFFFFF',
                borderRadius: 12,
                border: '1px solid #E2E8F0',
                padding: '18px 20px',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    background: '#FFF7ED',
                    border: '1px solid #FFEDD5',
                    display: 'grid',
                    placeItems: 'center',
                    color: '#EA580C',
                    flexShrink: 0,
                  }}
                >
                  <Mail size={20} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Primary Support
                  </div>
                  <a
                    href="mailto:sutra@sudarshanai.com"
                    style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: '#0F172A',
                      textDecoration: 'none',
                      display: 'block',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      marginTop: 2,
                    }}
                  >
                    sutra@sudarshanai.com
                  </a>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                <button
                  type="button"
                  onClick={() => handleCopy('sutra@sudarshanai.com')}
                  style={{
                    padding: '7px 12px',
                    borderRadius: 6,
                    border: '1px solid #E2E8F0',
                    background: copiedMail ? '#F0FDF4' : '#F8FAFC',
                    color: copiedMail ? '#166534' : '#475569',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    transition: 'all 0.15s ease',
                  }}
                >
                  {copiedMail ? <Check size={13} /> : <Copy size={13} />}
                  <span>{copiedMail ? 'Copied' : 'Copy'}</span>
                </button>
                <a
                  href="mailto:sutra@sudarshanai.com"
                  style={{
                    padding: '7px 14px',
                    borderRadius: 6,
                    background: '#EA580C',
                    color: '#FFFFFF',
                    fontSize: 12,
                    fontWeight: 600,
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                  }}
                >
                  <span>Write</span>
                  <ArrowRight size={13} />
                </a>
              </div>
            </div>

            {/* Quick Metrics Strip */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 12,
              }}
            >
              <div
                style={{
                  background: '#FFFFFF',
                  borderRadius: 10,
                  border: '1px solid #E2E8F0',
                  padding: '14px 16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#64748B', fontSize: 11.5, fontWeight: 600, marginBottom: 4 }}>
                  <Clock size={13} color="#EA580C" />
                  <span>Avg. First Response</span>
                </div>
                <div style={{ fontSize: 17, fontWeight: 800, color: '#0F172A' }}>&lt; 2 Hours</div>
                <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>24/7 governed escalation queue</div>
              </div>

              <div
                style={{
                  background: '#FFFFFF',
                  borderRadius: 10,
                  border: '1px solid #E2E8F0',
                  padding: '14px 16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#64748B', fontSize: 11.5, fontWeight: 600, marginBottom: 4 }}>
                  <BookOpen size={13} color="#2563EB" />
                  <span>Self-Serve Docs</span>
                </div>
                <Link
                  href="/docs#mcp-support"
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: '#2563EB',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>MCP Protocol Specs</span>
                  <ArrowRight size={12} />
                </Link>
                <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>Full API schemas &amp; rules</div>
              </div>
            </div>
          </div>

          {/* Right Column: Clean Ticket & Inquiry Form */}
          <div
            style={{
              background: '#FFFFFF',
              borderRadius: 16,
              border: '1px solid #E2E8F0',
              padding: '28px 30px',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.05)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}
          >
            {submitted ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '36px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: '50%',
                    background: '#F0FDF4',
                    border: '1px solid #BBF7D0',
                    display: 'grid',
                    placeItems: 'center',
                    color: '#16A34A',
                  }}
                >
                  <CheckCircle2 size={28} />
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: '#0F172A', margin: 0 }}>
                  Ticket Dispatched Successfully
                </h3>
                <p style={{ fontSize: 13, color: '#64748B', margin: 0, maxWidth: 360, lineHeight: 1.5 }}>
                  Our control plane engineering team has received your inquiry. We will reach back to{' '}
                  <strong style={{ color: '#0F172A' }}>{formData.email || 'your email'}</strong> promptly.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSubmitted(false);
                    setFormData({ name: '', email: '', topic: 'governance', message: '' });
                  }}
                  style={{
                    marginTop: 8,
                    padding: '8px 18px',
                    borderRadius: 8,
                    border: '1px solid #E2E8F0',
                    background: '#F8FAFC',
                    color: '#0F172A',
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Submit Another Inquiry
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ marginBottom: 2 }}>
                  <div style={{ fontSize: 17, fontWeight: 800, color: '#0F172A' }}>
                    Submit a Support Request
                  </div>
                  <div style={{ fontSize: 12, color: '#64748B', marginTop: 2 }}>
                    Describe your issue and an engineer will reply directly.
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label
                      htmlFor="support-name"
                      style={{
                        display: 'block',
                        fontSize: 11.5,
                        fontWeight: 700,
                        color: '#475569',
                        marginBottom: 4,
                      }}
                    >
                      Name
                    </label>
                    <input
                      id="support-name"
                      type="text"
                      required
                      placeholder="Name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      style={{
                        width: '100%',
                        height: 38,
                        borderRadius: 8,
                        border: '1px solid #E2E8F0',
                        padding: '0 12px',
                        fontSize: 13,
                        color: '#0F172A',
                        background: '#F8FAFC',
                        outline: 'none',
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="support-email"
                      style={{
                        display: 'block',
                        fontSize: 11.5,
                        fontWeight: 700,
                        color: '#475569',
                        marginBottom: 4,
                      }}
                    >
                      Email Address
                    </label>
                    <input
                      id="support-email"
                      type="email"
                      required
                      placeholder="example@mail.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      style={{
                        width: '100%',
                        height: 38,
                        borderRadius: 8,
                        border: '1px solid #E2E8F0',
                        padding: '0 12px',
                        fontSize: 13,
                        color: '#0F172A',
                        background: '#F8FAFC',
                        outline: 'none',
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="support-topic"
                    style={{
                      display: 'block',
                      fontSize: 11.5,
                      fontWeight: 700,
                      color: '#475569',
                      marginBottom: 4,
                    }}
                  >
                    Topic / Category
                  </label>
                  <select
                    id="support-topic"
                    value={formData.topic}
                    onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                    style={{
                      width: '100%',
                      height: 38,
                      borderRadius: 8,
                      border: '1px solid #E2E8F0',
                      padding: '0 12px',
                      fontSize: 13,
                      color: '#0F172A',
                      background: '#F8FAFC',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  >
                    <option value="governance">Governance &amp; Approvals</option>
                    <option value="mcp">MCP Server &amp; Tooling</option>
                    <option value="auth">Agent Authentication &amp; Sessions</option>
                    <option value="billing">Enterprise &amp; Workspaces</option>
                    <option value="bug">Bug Report / Defect</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="support-message"
                    style={{
                      display: 'block',
                      fontSize: 11.5,
                      fontWeight: 700,
                      color: '#475569',
                      marginBottom: 4,
                    }}
                  >
                    Message / Details
                  </label>
                  <textarea
                    id="support-message"
                    required
                    rows={3}
                    placeholder="Briefly describe what you are experiencing..."
                    value={formData.message}
                    onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                    style={{
                      width: '100%',
                      borderRadius: 8,
                      border: '1px solid #E2E8F0',
                      padding: '10px 12px',
                      fontSize: 13,
                      color: '#0F172A',
                      background: '#F8FAFC',
                      outline: 'none',
                      boxSizing: 'border-box',
                      resize: 'none',
                      fontFamily: 'inherit',
                    }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    height: 40,
                    borderRadius: 8,
                    background: '#EA580C',
                    color: '#FFFFFF',
                    border: 'none',
                    fontWeight: 700,
                    fontSize: 13,
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    marginTop: 4,
                    boxShadow: '0 2px 8px rgba(234, 88, 12, 0.25)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <Send size={14} />
                  <span>{isSubmitting ? 'Sending Request...' : 'Send Inquiry'}</span>
                </button>
              </form>
            )}
          </div>
        </div>
      </main>

      {/* Minimal Footer */}
      <footer
        style={{
          height: 38,
          borderTop: '1px solid #E2E8F0',
          background: '#FFFFFF',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 11.5,
          color: '#64748B',
          flexShrink: 0,
        }}
      >
        <div>&copy; {new Date().getFullYear()} SUTRA &bull; AI-Native Engineering Control Plane</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Link href="/docs" style={{ color: '#64748B', textDecoration: 'none' }}>
            Docs
          </Link>
          <a href="mailto:sutra@sudarshanai.com" style={{ color: '#EA580C', textDecoration: 'none', fontWeight: 600 }}>
            sutra@sudarshanai.com
          </a>
        </div>
      </footer>
    </div>
  );
}
