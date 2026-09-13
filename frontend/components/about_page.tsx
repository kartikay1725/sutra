'use client';

import React, { useState } from "react";
import Link from "next/link";
import {
  Menu,
  X,
  ArrowRight,
  BookOpen,
} from "lucide-react";

export function AboutPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "AboutPage",
        "@id": "https://sutra.sudarshanai.com/about/#webpage",
        "url": "https://sutra.sudarshanai.com/about",
        "name": "About SUTRA — AI-Native Engineering Control Plane",
        "description": "Learn about SUTRA by Sudarshan Harness: an AI-native engineering control plane providing bounded authority, real Git workflows, and human review for autonomous engineering.",
        "isPartOf": {
          "@type": "WebSite",
          "name": "SUTRA — AI-Native Engineering Control Plane",
          "url": "https://sutra.sudarshanai.com"
        },
        "about": {
          "@type": "SoftwareApplication",
          "name": "SUTRA",
          "description": "AI-native engineering control plane by Sudarshan Harness"
        }
      }
    ]
  };

  return (
    <div style={{ background: "#090C10", minHeight: "100vh", color: "#F2F5F8", overflowX: "hidden", position: "relative" }}>
      {/* JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />

      {/* Navigation */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: "rgba(16, 21, 28, 0.88)",
          backdropFilter: "blur(20px)",
          borderBottom: "1px solid #212836",
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          {/* Brand Left */}
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                overflow: "hidden",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "#000",
                border: "1px solid #212836",
              }}
            >
              <img
                src="/logo.svg"
                alt="SUTRA Logo"
                style={{ height: "100%", width: "100%", objectFit: "contain" }}
              />
            </div>
            <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "0.04em", color: "#F2F5F8" }}>
              SUTRA
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                background: "rgba(59, 130, 246, 0.12)",
                border: "1px solid rgba(59, 130, 246, 0.28)",
                color: "#60A5FA",
                padding: "2px 7px",
                borderRadius: 999,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
              }}
            >
              Beta
            </span>
          </Link>

          {/* Desktop Nav Links */}
          <nav
            style={{
              display: "none",
              alignItems: "center",
              gap: 32,
            }}
            className="desktop-nav"
          >
            <Link href="/#product" style={{ fontSize: 14, color: "#A8B1BD", textDecoration: "none" }}>
              Product
            </Link>
            <Link href="/#how-it-works" style={{ fontSize: 14, color: "#A8B1BD", textDecoration: "none" }}>
              How It Works
            </Link>
            <Link href="/about" style={{ fontSize: 14, color: "#F2F5F8", fontWeight: 600, textDecoration: "none" }}>
              About
            </Link>
            <Link
              href="/docs"
              style={{
                fontSize: 13,
                color: "#60A5FA",
                textDecoration: "none",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "4px 10px",
                borderRadius: 6,
                background: "rgba(59, 130, 246, 0.08)",
                border: "1px solid rgba(59, 130, 246, 0.2)",
              }}
            >
              <BookOpen size={13} />
              Docs
            </Link>
          </nav>

          {/* Right CTA */}
          <div style={{ display: "none", alignItems: "center", gap: 14 }} className="desktop-nav">
            <Link
              href="/login"
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: "#F2F5F8",
                textDecoration: "none",
                padding: "8px 14px",
              }}
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="btn primary"
              style={{
                padding: "8px 20px",
                borderRadius: 999,
                fontSize: 13,
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Join the Beta
            </Link>
          </div>

          {/* Mobile Menu Toggle Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "1px solid #212836",
              borderRadius: 8,
              padding: 6,
              color: "#F2F5F8",
              cursor: "pointer",
            }}
            aria-label="Toggle navigation menu"
            className="mobile-toggle"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile Dropdown */}
        {mobileMenuOpen && (
          <div
            style={{
              padding: "16px 24px 24px",
              borderTop: "1px solid #212836",
              background: "#10151C",
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <Link
              href="/#product"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#F2F5F8", textDecoration: "none" }}
            >
              Product
            </Link>
            <Link
              href="/#how-it-works"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#F2F5F8", textDecoration: "none" }}
            >
              How It Works
            </Link>
            <Link
              href="/about"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#F2F5F8", fontWeight: 600, textDecoration: "none" }}
            >
              About
            </Link>
            <Link
              href="/docs"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#60A5FA", textDecoration: "none", fontWeight: 600 }}
            >
              Documentation & Guides
            </Link>
            <div style={{ height: 1, background: "#212836", margin: "6px 0" }} />
            <Link
              href="/login"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 14, color: "#A8B1BD", textDecoration: "none" }}
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="btn primary"
              onClick={() => setMobileMenuOpen(false)}
              style={{
                textAlign: "center",
                justifyContent: "center",
                textDecoration: "none",
                marginTop: 4,
              }}
            >
              Join the Beta
            </Link>
          </div>
        )}
      </header>

      {/* ABOUT HERO */}
      <section
        style={{
          maxWidth: 1000,
          margin: "0 auto",
          padding: "80px 24px 40px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 14px",
            borderRadius: 999,
            background: "rgba(59, 130, 246, 0.1)",
            border: "1px solid rgba(59, 130, 246, 0.28)",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "#60A5FA",
            marginBottom: 24,
          }}
        >
          ABOUT SUTRA
        </div>

        <h1
          style={{
            fontSize: "clamp(30px, 5vw, 50px)",
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: "-0.03em",
            color: "#F2F5F8",
            marginBottom: 24,
          }}
        >
          Building the control layer for AI software agents.
        </h1>

        <p
          style={{
            fontSize: "clamp(16px, 2vw, 19px)",
            lineHeight: 1.65,
            color: "#A8B1BD",
            maxWidth: 780,
            margin: "0 auto",
          }}
        >
          SUTRA is an infrastructure layer for giving AI agents a real engineering identity, bounded access, verifiable execution, and human oversight.
        </p>
      </section>

      {/* ABOUT — THE PROBLEM */}
      <section
        style={{
          maxWidth: 860,
          margin: "0 auto",
          padding: "60px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(22px, 3.5vw, 32px)",
            fontWeight: 700,
            lineHeight: 1.25,
            color: "#F2F5F8",
            marginBottom: 20,
          }}
        >
          Software engineering is more than code generation.
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#A8B1BD",
            marginBottom: 16,
          }}
        >
          An AI system can generate a function in seconds. Shipping that function responsibly requires much more: identity, authorization, repository access, version control, testing, review, and controlled execution.
        </p>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#707A88",
            margin: 0,
          }}
        >
          SUTRA focuses on that engineering layer.
        </p>
      </section>

      {/* ABOUT — PRINCIPLE */}
      <section
        style={{
          maxWidth: 860,
          margin: "0 auto",
          padding: "60px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(22px, 3.5vw, 32px)",
            fontWeight: 700,
            lineHeight: 1.25,
            color: "#F2F5F8",
            marginBottom: 20,
          }}
        >
          AI should be able to act without becoming indistinguishable from a human administrator.
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#A8B1BD",
            margin: 0,
          }}
        >
          SUTRA is designed around a simple principle: agents should have enough authority to do useful engineering work, but that authority should be explicit, bounded, observable, and revocable.
        </p>
      </section>

      {/* ABOUT — ENGINEERING MODEL */}
      <section
        style={{
          maxWidth: 1000,
          margin: "0 auto",
          padding: "60px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <h2
            style={{
              fontSize: "clamp(22px, 3.5vw, 32px)",
              fontWeight: 700,
              lineHeight: 1.25,
              color: "#F2F5F8",
              marginBottom: 12,
            }}
          >
            Identity → Authority → Execution → Evidence → Verification
          </h2>
          <p style={{ fontSize: 15, color: "#A8B1BD", margin: 0 }}>
            The architectural model behind bounded agent execution.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
          }}
        >
          {[
            { tag: "IDENTITY", text: "An external agent is represented by a distinct SUTRA Agent identity." },
            { tag: "AUTHORITY", text: "Access is explicitly scoped to repositories and capabilities." },
            { tag: "EXECUTION", text: "Agents can perform real engineering operations through controlled interfaces." },
            { tag: "EVIDENCE", text: "Engineering work is tied to real commits, changed files, diff statistics, CI, and review state." },
            { tag: "VERIFICATION", text: "System policies and human review determine whether work can progress." },
            { tag: "CONTROL", text: "Agent access can be revoked and sessions expire." },
          ].map((item) => (
            <div
              key={item.tag}
              style={{
                padding: "22px",
                borderRadius: 12,
                background: "#10151C",
                border: "1px solid #212836",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.12em",
                  color: "#3B82F6",
                  marginBottom: 8,
                }}
              >
                {item.tag}
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.6, color: "#A8B1BD", margin: 0 }}>
                {item.text}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ABOUT — HUMAN CONTROL */}
      <section
        style={{
          maxWidth: 860,
          margin: "0 auto",
          padding: "60px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(22px, 3.5vw, 32px)",
            fontWeight: 700,
            lineHeight: 1.25,
            color: "#F2F5F8",
            marginBottom: 20,
          }}
        >
          Humans remain the final authority.
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#A8B1BD",
            marginBottom: 16,
          }}
        >
          Agents can perform engineering work, but they do not become the final approver of their own work.
        </p>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#707A88",
            margin: 0,
          }}
        >
          Review, policy, repository authorization, and merge controls remain separate from agent execution.
        </p>
      </section>

      {/* ABOUT — WHAT SUTRA IS NOT */}
      <section
        style={{
          maxWidth: 860,
          margin: "0 auto",
          padding: "60px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(22px, 3.5vw, 32px)",
            fontWeight: 700,
            lineHeight: 1.25,
            color: "#F2F5F8",
            marginBottom: 20,
          }}
        >
          SUTRA is not another coding chatbot.
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#707A88",
            margin: 0,
          }}
        >
          SUTRA focuses on the system around the model: identity, authorization, execution, Git, evidence, verification, and human control.
        </p>
      </section>

      {/* ABOUT — Beta */}
      <section
        style={{
          maxWidth: 860,
          margin: "0 auto 80px",
          padding: "56px 24px",
          background: "#10151C",
          border: "1px solid #212836",
          borderRadius: 20,
          textAlign: "center",
          boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(24px, 4vw, 36px)",
            fontWeight: 800,
            color: "#F2F5F8",
            marginBottom: 14,
          }}
        >
          Beta
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.6,
            color: "#A8B1BD",
            maxWidth: 600,
            margin: "0 auto 28px",
          }}
        >
          We are currently testing SUTRA with a limited group of users and real engineering workflows.
        </p>
        <Link
          href="/register"
          className="btn primary"
          style={{
            padding: "12px 32px",
            borderRadius: 999,
            fontSize: 14,
            fontWeight: 600,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          Join the Beta
          <ArrowRight size={16} />
        </Link>
      </section>

      {/* FOOTER */}
      <footer
        style={{
          borderTop: "1px solid #212836",
          background: "#090C10",
          padding: "48px 24px 36px",
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 24,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <div style={{ width: 24, height: 24, borderRadius: 6, overflow: "hidden", background: "#000" }}>
                <img src="/logo.svg" alt="SUTRA Logo" style={{ height: "100%", width: "100%", objectFit: "contain" }} />
              </div>
              <span style={{ fontSize: 16, fontWeight: 800, color: "#F2F5F8" }}>SUTRA</span>
            </div>
            <div style={{ fontSize: 13, color: "#A8B1BD" }}>
              AI agents that can actually ship software.
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap", fontSize: 13 }}>
            <Link href="/#product" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              Product
            </Link>
            <Link href="/#how-it-works" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              How It Works
            </Link>
            <Link href="/about" style={{ color: "#F2F5F8", fontWeight: 600, textDecoration: "none" }}>
              About
            </Link>
            <Link href="/docs" style={{ color: "#60A5FA", textDecoration: "none", fontWeight: 600 }}>
              Docs
            </Link>
            <Link href="/security" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              Security
            </Link>
            <Link href="/login" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              Sign In
            </Link>
            <Link href="/register" style={{ color: "#3B82F6", textDecoration: "none", fontWeight: 600 }}>
              Join the Beta
            </Link>
            <a href="mailto:sutra@sudarshanai.com" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              Contact Us
            </a>
          </div>
        </div>

        <div
          style={{
            maxWidth: 1200,
            margin: "32px auto 0",
            paddingTop: 24,
            borderTop: "1px solid #212836",
            fontSize: 11,
            color: "#707A88",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>© {new Date().getFullYear()} SUTRA. A Sudarshan Harness Product. All rights reserved.</div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span>Contact us at <a href="mailto:sutra@sudarshanai.com" style={{ color: "#60A5FA", textDecoration: "none" }}>sutra@sudarshanai.com</a></span>
            <span>•</span>
            <span>AI-Native Engineering Control Plane</span>
          </div>
        </div>
      </footer>

      {/* Responsive media query helper */}
      <style jsx global>{`
        @media (min-width: 768px) {
          .desktop-nav {
            display: flex !important;
          }
          .mobile-toggle {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
