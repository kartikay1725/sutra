'use client';

import React, { useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  GitBranch,
  FileCode,
  CheckCircle2,
  Lock,
  Terminal,
  Cpu,
  ChevronDown,
  ArrowRight,
  Menu,
  X,
  Workflow,
  Eye,
  CheckCheck,
  BookOpen
} from "lucide-react";
import { SpotlightCard, ShimmerButton, GridBackground } from "./ui/aceternity";
import { trackEvent } from "./analytics";

export function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": "https://sutra.sudarshanai.com/#organization",
        "name": "Sudarshan Harness",
        "url": "https://sudarshanai.com",
        "logo": "https://sutra.sudarshanai.com/og-image.png",
        "description": "Provider of engineering harness systems and governed autonomous software engineering platforms."
      },
      {
        "@type": "SoftwareApplication",
        "@id": "https://sutra.sudarshanai.com/#software",
        "name": "SUTRA",
        "url": "https://sutra.sudarshanai.com",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Cloud, Linux, macOS, Windows",
        "description": "SUTRA is an AI-native engineering control plane for governed autonomous software engineering with bounded authority, real Git workflows, and human review.",
        "creator": {
          "@id": "https://sutra.sudarshanai.com/#organization"
        },
        "offers": {
          "@type": "Offer",
          "price": "0",
          "priceCurrency": "USD",
          "availability": "https://schema.org/PreOrder"
        }
      },
      {
        "@type": "WebSite",
        "@id": "https://sutra.sudarshanai.com/#website",
        "url": "https://sutra.sudarshanai.com",
        "name": "SUTRA — AI-Native Engineering Control Plane",
        "publisher": {
          "@id": "https://sutra.sudarshanai.com/#organization"
        }
      },
      {
        "@type": "WebPage",
        "@id": "https://sutra.sudarshanai.com/#webpage",
        "url": "https://sutra.sudarshanai.com",
        "name": "SUTRA — AI-Native Engineering Control Plane",
        "description": "SUTRA is an AI-native engineering control plane by Sudarshan Harness for governed autonomous software engineering.",
        "isPartOf": {
          "@id": "https://sutra.sudarshanai.com/#website"
        }
      },
      {
        "@type": "FAQPage",
        "@id": "https://sutra.sudarshanai.com/#faq",
        "mainEntity": [
          {
            "@type": "Question",
            "name": "What is SUTRA?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "SUTRA is an AI-native engineering control plane built by Sudarshan Harness. It provides governed autonomous software engineering by combining scoped agent identity, cryptographic event verification, real Git lifecycles, and mandatory human review."
            }
          },
          {
            "@type": "Question",
            "name": "Who makes SUTRA?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "SUTRA is developed by Sudarshan Harness (sudarshanai.com) as the control plane for autonomous software engineering."
            }
          },
          {
            "@type": "Question",
            "name": "How is SUTRA different from GitHub?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "GitHub serves as the authoritative repository substrate for branches, commits, PRs, and CI. SUTRA serves as the control plane that enforces agent capabilities, temporary session leases, change provenance, and governed human approval before merges."
            }
          },
          {
            "@type": "Question",
            "name": "What is an AI-native engineering control plane?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "An AI-native engineering control plane is an orchestration and governance system designed specifically for autonomous AI agents. It ensures agents operate with bounded permissions, traceable commits, and clear separation of execution from approval."
            }
          },
          {
            "@type": "Question",
            "name": "Can an AI agent approve its own work in SUTRA?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "No. SUTRA strictly separates execution from approval. AI agents can write code, propose changes, and run CI checks, but human approval is strictly required to merge governed changes."
            }
          },
          {
            "@type": "Question",
            "name": "How does SUTRA control AI agents?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "SUTRA enforces explicit repository capability grants, short-lived AgentSessions (15-minute absolute leases, 120-second idle timeouts), pre-receive Git hook validation, and immutable audit logs."
            }
          },
          {
            "@type": "Question",
            "name": "Who is SUTRA for?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "SUTRA is built for software engineering teams, enterprise organizations, and developers deploying autonomous coding agents who require enterprise governance, auditability, and safety."
            }
          }
        ]
      }
    ]
  };

  const faqs = [
    {
      q: "What is SUTRA?",
      a: "SUTRA is an AI-native engineering control plane built by Sudarshan Harness. It enables governed autonomous software engineering with scoped agent identity, real Git workflows, and mandatory human review."
    },
    {
      q: "Who makes SUTRA?",
      a: "SUTRA is developed by Sudarshan Harness (sudarshanai.com) as the authoritative control plane for autonomous software engineering."
    },
    {
      q: "How is SUTRA different from GitHub?",
      a: "GitHub serves as the repository substrate for code and branches. SUTRA is the control plane governing agent permissions, AgentSession leases, cryptographic change provenance, and merge approval policies."
    },
    {
      q: "What is an AI-native engineering control plane?",
      a: "It is an orchestration layer built specifically for autonomous agents, enforcing lease-bound Git access, capability validation, and strict separation between agent code execution and human merge authorization."
    },
    {
      q: "Can an AI agent approve its own work in SUTRA?",
      a: "No. SUTRA strictly enforces that agents can propose changes and run CI, but human approval is mandatory to merge governed changes."
    },
    {
      q: "How does SUTRA control AI agents?",
      a: "SUTRA uses capability-based access control, short-lived 15-minute AgentSessions, Git pre-receive validation hooks, and tamper-resistant audit logs."
    },
    {
      q: "Who is SUTRA for?",
      a: "Engineering teams and enterprise organizations adopting autonomous AI agents who require strict security, governance, and audit trails."
    }
  ];

  return (
    <div style={{ background: "#090C10", minHeight: "100vh", color: "#F2F5F8", overflowX: "hidden", position: "relative" }}>
      {/* JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />

      {/* Subtle top radiance */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          transform: "translateX(-50%)",
          width: "100%",
          maxWidth: 1200,
          height: 520,
          background: "radial-gradient(ellipse at 50% 0%, rgba(59, 130, 246, 0.12) 0%, rgba(99, 102, 241, 0.04) 45%, transparent 70%)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      {/* 1. NAVIGATION */}
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
              Private Beta
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
            <a href="#product" style={{ fontSize: 14, color: "#A8B1BD", textDecoration: "none", fontWeight: 500 }}>
              Product
            </a>
            <a href="#how-it-works" style={{ fontSize: 14, color: "#A8B1BD", textDecoration: "none", fontWeight: 500 }}>
              How It Works
            </a>
            <Link href="/about" style={{ fontSize: 14, color: "#A8B1BD", textDecoration: "none", fontWeight: 500 }}>
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
              onClick={() => trackEvent("click_login", "navigation", "nav_sign_in")}
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
              onClick={() => trackEvent("click_cta", "navigation", "nav_join_private_beta")}
              style={{
                padding: "8px 20px",
                borderRadius: 999,
                fontSize: 13,
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Join the Private Beta
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
            <a
              href="#product"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#F2F5F8", textDecoration: "none" }}
            >
              Product
            </a>
            <a
              href="#how-it-works"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#F2F5F8", textDecoration: "none" }}
            >
              How It Works
            </a>
            <Link
              href="/about"
              onClick={() => setMobileMenuOpen(false)}
              style={{ fontSize: 15, color: "#F2F5F8", textDecoration: "none" }}
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
              Join the Private Beta
            </Link>
          </div>
        )}
      </header>

      {/* 2. HERO */}
      <GridBackground>
        <section
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            padding: "90px 24px 70px",
            textAlign: "center",
            position: "relative",
            zIndex: 10,
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
            AI-NATIVE ENGINEERING CONTROL PLANE · SUDARSHAN HARNESS
          </div>

          <h1
            style={{
              fontSize: "clamp(32px, 5.5vw, 56px)",
              fontWeight: 800,
              lineHeight: 1.12,
              letterSpacing: "-0.03em",
              maxWidth: 920,
              margin: "0 auto 24px",
              color: "#F2F5F8",
            }}
          >
            AI agents that can actually ship software.
          </h1>

          <p
            style={{
              fontSize: "clamp(16px, 2vw, 19px)",
              lineHeight: 1.6,
              color: "#A8B1BD",
              maxWidth: 780,
              margin: "0 auto 36px",
            }}
          >
            SUTRA is an AI-native engineering control plane by Sudarshan Harness for governed autonomous software engineering — combining scoped agent identity, real Git lifecycles, and mandatory human review.
          </p>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
              flexWrap: "wrap",
              marginBottom: 64,
            }}
          >
            <Link
              href="/register"
              style={{ textDecoration: "none" }}
              onClick={() => trackEvent("click_cta", "marketing", "hero_join_private_beta")}
            >
              <ShimmerButton style={{ padding: "14px 34px", fontSize: 15 }}>
                Join the Private Beta
                <ArrowRight size={16} />
              </ShimmerButton>
            </Link>

            <a
              href="#how-it-works"
              className="btn"
              onClick={() => trackEvent("click_anchor", "marketing", "hero_how_it_works")}
              style={{
                padding: "14px 28px",
                borderRadius: 999,
                fontSize: 15,
                fontWeight: 500,
                textDecoration: "none",
                color: "#F2F5F8",
                background: "#171D26",
                border: "1px solid #212836",
              }}
            >
              See How SUTRA Works
            </a>

            <Link
              href="/docs"
              className="btn guide"
              onClick={() => trackEvent("click_docs", "marketing", "hero_docs")}
              style={{
                padding: "14px 22px",
                borderRadius: 999,
                fontSize: 14,
                height: "auto",
                textDecoration: "none",
              }}
            >
              <BookOpen size={15} />
              Read Documentation
            </Link>
          </div>

          {/* Hero Visual: Task -> Agent -> Code -> Git -> CI -> Review -> Merge */}
          <div
            style={{
              maxWidth: 1020,
              margin: "0 auto",
              background: "#10151C",
              border: "1px solid #212836",
              borderRadius: 16,
              padding: "32px 24px",
              boxShadow: "0 24px 60px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 20,
                flexWrap: "wrap",
                gap: 10,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: "#60A5FA",
                  fontWeight: 700,
                }}
              >
                Controlled Engineering Execution Pipeline
              </div>
              <Link
                href="/docs#git-http-agent-workflow"
                style={{
                  fontSize: 12,
                  color: "#A8B1BD",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                Workflow Guide <ArrowRight size={12} />
              </Link>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(115px, 1fr))",
                gap: 12,
                alignItems: "center",
              }}
            >
              {[
                { title: "Task", icon: Terminal, desc: "Intent Defined", color: "#3B82F6" },
                { title: "Agent", icon: Cpu, desc: "Scoped Session", color: "#6366F1" },
                { title: "Code", icon: FileCode, desc: "Files Changed", color: "#60A5FA" },
                { title: "Git", icon: GitBranch, desc: "Real Commits", color: "#3B82F6" },
                { title: "CI", icon: CheckCircle2, desc: "Automated Checks", color: "#22C55E" },
                { title: "Review", icon: Eye, desc: "Human Sign-off", color: "#F59E0B" },
                { title: "Merge", icon: CheckCheck, desc: "Verified Commit", color: "#22C55E" },
              ].map((step) => (
                <div
                  key={step.title}
                  style={{
                    background: "#171D26",
                    border: "1px solid #212836",
                    borderRadius: 10,
                    padding: "16px 10px",
                    textAlign: "center",
                    position: "relative",
                    transition: "border-color 0.18s",
                  }}
                >
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: "50%",
                      background: "rgba(59, 130, 246, 0.08)",
                      border: `1px solid ${step.color}50`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 10px",
                      color: step.color,
                    }}
                  >
                    <step.icon size={16} />
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#F2F5F8", marginBottom: 2 }}>
                    {step.title}
                  </div>
                  <div style={{ fontSize: 11, color: "#707A88" }}>{step.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </GridBackground>

      {/* 3. PROBLEM SECTION */}
      <section
        style={{
          maxWidth: 900,
          margin: "0 auto",
          padding: "80px 24px",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(24px, 3.5vw, 36px)",
            fontWeight: 700,
            lineHeight: 1.25,
            letterSpacing: "-0.02em",
            color: "#F2F5F8",
            marginBottom: 24,
          }}
        >
          Writing code is only part of engineering.
        </h2>
        <p
          style={{
            fontSize: "17px",
            lineHeight: 1.7,
            color: "#A8B1BD",
            marginBottom: 20,
          }}
        >
          AI systems can generate code quickly. Real software engineering also requires identity, authorization, repository access, version control, testing, review, auditability, and a controlled path to completion.
        </p>
        <p
          style={{
            fontSize: "17px",
            lineHeight: 1.7,
            color: "#707A88",
            margin: 0,
          }}
        >
          SUTRA focuses on the layer between an AI model and a real engineering workflow.
        </p>
      </section>

      {/* 4. WHAT SUTRA DOES */}
      <section
        id="product"
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding: "60px 24px 80px",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#3B82F6", marginBottom: 12 }}>
            CORE CAPABILITIES
          </div>
          <h2
            style={{
              fontSize: "clamp(26px, 4vw, 40px)",
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              color: "#F2F5F8",
              margin: 0,
            }}
          >
            Give AI agents the ability to do real engineering work.
          </h2>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 20,
          }}
        >
          {/* Card 1 */}
          <SpotlightCard spotlightColor="rgba(59, 130, 246, 0.16)">
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(59, 130, 246, 0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#60A5FA", marginBottom: 18 }}>
              <ShieldCheck size={20} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 600, color: "#F2F5F8", margin: "0 0 10px 0" }}>
              Controlled Agent Identity
            </h3>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: "#A8B1BD", margin: "0 0 16px 0" }}>
              Every external agent gets a distinct SUTRA identity and short-lived session instead of operating through a human's credentials.
            </p>
            <Link href="/docs#agent-registration-onboarding" className="btn guide" style={{ fontSize: 11, height: 28, padding: "0 10px" }}>
              Identity Guide <ArrowRight size={11} />
            </Link>
          </SpotlightCard>

          {/* Card 2 */}
          <SpotlightCard spotlightColor="rgba(99, 102, 241, 0.16)">
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(99, 102, 241, 0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#818CF8", marginBottom: 18 }}>
              <Lock size={20} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 600, color: "#F2F5F8", margin: "0 0 10px 0" }}>
              Repository-Scoped Authority
            </h3>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: "#A8B1BD", margin: "0 0 16px 0" }}>
              Agents only receive access to repositories and capabilities explicitly granted to them.
            </p>
            <Link href="/docs#agent-session-lifecycle" className="btn guide" style={{ fontSize: 11, height: 28, padding: "0 10px" }}>
              Authority Guide <ArrowRight size={11} />
            </Link>
          </SpotlightCard>

          {/* Card 3 */}
          <SpotlightCard spotlightColor="rgba(34, 197, 94, 0.16)">
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(34, 197, 94, 0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#22C55E", marginBottom: 18 }}>
              <Workflow size={20} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 600, color: "#F2F5F8", margin: "0 0 10px 0" }}>
              Real Engineering Workflow
            </h3>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: "#A8B1BD", margin: "0 0 16px 0" }}>
              Agents can work through branches, commits, Changes, Pull Requests, CI, review, and merge.
            </p>
            <Link href="/docs#git-http-agent-workflow" className="btn guide" style={{ fontSize: 11, height: 28, padding: "0 10px" }}>
              Workflow Guide <ArrowRight size={11} />
            </Link>
          </SpotlightCard>

          {/* Card 4 */}
          <SpotlightCard spotlightColor="rgba(245, 158, 11, 0.16)">
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(245, 158, 11, 0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#F59E0B", marginBottom: 18 }}>
              <Eye size={20} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 600, color: "#F2F5F8", margin: "0 0 10px 0" }}>
              Human Control
            </h3>
            <p style={{ fontSize: 14, lineHeight: 1.6, color: "#A8B1BD", margin: "0 0 16px 0" }}>
              Agents cannot approve their own work or bypass repository, review, or merge controls.
            </p>
            <Link href="/docs#changes-pull-requests-ci" className="btn guide" style={{ fontSize: 11, height: 28, padding: "0 10px" }}>
              Governance Guide <ArrowRight size={11} />
            </Link>
          </SpotlightCard>
        </div>
      </section>

      {/* 5. HOW SUTRA WORKS */}
      <section
        id="how-it-works"
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "80px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#3B82F6", marginBottom: 12 }}>
            STEP-BY-STEP LIFECYCLE
          </div>
          <h2
            style={{
              fontSize: "clamp(26px, 4vw, 40px)",
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              color: "#F2F5F8",
              margin: 0,
            }}
          >
            How SUTRA works
          </h2>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {[
            {
              step: "01",
              title: "Connect your Agent",
              desc: "Register an external AI agent with SUTRA.",
              guide: "/docs#agent-registration-onboarding",
            },
            {
              step: "02",
              title: "Give it bounded access",
              desc: "Choose the repository and capabilities that agent is allowed to use.",
              guide: "/docs#agent-session-lifecycle",
            },
            {
              step: "03",
              title: "Let it work",
              desc: "The agent receives a short-lived session and performs real engineering work.",
              guide: "/docs#git-http-agent-workflow",
            },
            {
              step: "04",
              title: "Verify the result",
              desc: "SUTRA records the commit, changed files, diff evidence, CI state, and review state.",
              guide: "/docs#changes-pull-requests-ci",
            },
            {
              step: "05",
              title: "Keep the human in control",
              desc: "A human reviews and approves the work before protected changes are merged.",
              guide: "/docs#human-quickstart",
            },
          ].map((item) => (
            <div
              key={item.step}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 20,
                padding: "24px",
                borderRadius: 12,
                background: "#10151C",
                border: "1px solid #212836",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 20 }}>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 800,
                    fontFamily: "monospace",
                    color: "#60A5FA",
                    background: "rgba(59, 130, 246, 0.1)",
                    padding: "6px 12px",
                    borderRadius: 6,
                    lineHeight: 1,
                  }}
                >
                  {item.step}
                </div>
                <div>
                  <h3 style={{ fontSize: 18, fontWeight: 600, color: "#F2F5F8", margin: "0 0 6px 0" }}>
                    {item.title}
                  </h3>
                  <p style={{ fontSize: 14, lineHeight: 1.6, color: "#A8B1BD", margin: 0 }}>
                    {item.desc}
                  </p>
                </div>
              </div>

              <Link href={item.guide} className="btn guide" style={{ flexShrink: 0 }}>
                <BookOpen size={13} />
                View Guide
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* 6. AGENT IDENTITY & ACCESS CONTROL */}
      <section
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding: "80px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <h2
            style={{
              fontSize: "clamp(26px, 4vw, 38px)",
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              color: "#F2F5F8",
              marginBottom: 12,
            }}
          >
            Power without uncontrolled access.
          </h2>
          <p style={{ fontSize: 16, color: "#A8B1BD", margin: 0 }}>
            Agents should be capable. They should also be bounded.
          </p>
        </div>

        {/* Pipeline display */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            flexWrap: "wrap",
            marginBottom: 48,
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: "0.05em",
            color: "#60A5FA",
          }}
        >
          <span>Identity</span>
          <span style={{ color: "#707A88" }}>→</span>
          <span>Authority</span>
          <span style={{ color: "#707A88" }}>→</span>
          <span>Execution</span>
          <span style={{ color: "#707A88" }}>→</span>
          <span>Evidence</span>
          <span style={{ color: "#707A88" }}>→</span>
          <span>Verification</span>
          <span style={{ color: "#707A88" }}>→</span>
          <span>Human Control</span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: 18,
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

      {/* 7. ENGINEERING EVIDENCE */}
      <section
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "80px 24px",
          borderTop: "1px solid #212836",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(26px, 4vw, 38px)",
            fontWeight: 700,
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            color: "#F2F5F8",
            marginBottom: 16,
          }}
        >
          Every change leaves evidence.
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.6,
            color: "#A8B1BD",
            maxWidth: 700,
            margin: "0 auto 48px",
          }}
        >
          SUTRA connects an agent's engineering action to the artifacts and checks surrounding that action.
        </p>

        {/* Evidence Pipeline */}
        <div
          style={{
            background: "#10151C",
            border: "1px solid #212836",
            borderRadius: 16,
            padding: "36px 24px",
            maxWidth: 800,
            margin: "0 auto",
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 16,
              alignItems: "center",
            }}
          >
            {[
              { stage: "Agent", label: "Registered external agent with scoped capability" },
              { stage: "Commit", label: "Real Git commit" },
              { stage: "Changed Files", label: "File-level change evidence" },
              { stage: "Diff", label: "Actual additions and deletions" },
              { stage: "CI", label: "CI results" },
              { stage: "Review", label: "Human review" },
              { stage: "Merge", label: "Verified merge state" },
            ].map((step, idx, arr) => (
              <React.Fragment key={step.stage}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                    maxWidth: 560,
                    padding: "12px 20px",
                    background: "#171D26",
                    border: "1px solid #212836",
                    borderRadius: 10,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#3B82F6" }} />
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#F2F5F8" }}>{step.stage}</span>
                  </div>
                  <span style={{ fontSize: 13, color: "#A8B1BD", fontWeight: 500 }}>{step.label}</span>
                </div>
                {idx < arr.length - 1 && (
                  <div style={{ color: "#707A88", fontSize: 14 }}>↓</div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* 8. HUMAN CONTROL */}
      <section
        style={{
          maxWidth: 900,
          margin: "0 auto",
          padding: "80px 24px",
          borderTop: "1px solid #212836",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(26px, 4vw, 38px)",
            fontWeight: 700,
            lineHeight: 1.25,
            letterSpacing: "-0.02em",
            color: "#F2F5F8",
            marginBottom: 24,
          }}
        >
          Humans remain the final authority.
        </h2>
        <p
          style={{
            fontSize: 17,
            lineHeight: 1.7,
            color: "#A8B1BD",
            marginBottom: 20,
          }}
        >
          Agents can perform engineering work, but they do not become the final approver of their own work.
        </p>
        <p
          style={{
            fontSize: 17,
            lineHeight: 1.7,
            color: "#707A88",
            margin: 0,
          }}
        >
          Repository authorization, policy evaluation, review, and merge controls remain separate from agent execution.
        </p>
      </section>

      {/* 9. WORKFLOW VISUALIZATION */}
      <section
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "80px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#22C55E", marginBottom: 12 }}>
            TECHNICAL WORKFLOW
          </div>
          <h2
            style={{
              fontSize: "clamp(26px, 4vw, 38px)",
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              color: "#F2F5F8",
              margin: 0,
            }}
          >
            From Task to Verified Merge
          </h2>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
          }}
        >
          {[
            { phase: "TASK", text: "Define engineering intent.", icon: Terminal },
            { phase: "AGENT", text: "Execute with bounded authority.", icon: Cpu },
            { phase: "GIT", text: "Create real branches and commits.", icon: GitBranch },
            { phase: "CHANGE", text: "Record what changed.", icon: FileCode },
            { phase: "CI", text: "Verify the result.", icon: CheckCircle2 },
            { phase: "REVIEW", text: "Keep humans in control.", icon: Eye },
            { phase: "MERGE", text: "Complete the change only when allowed.", icon: CheckCheck },
          ].map((item) => (
            <div
              key={item.phase}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                padding: "18px 20px",
                borderRadius: 12,
                background: "#10151C",
                border: "1px solid #212836",
              }}
            >
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 8,
                  background: "rgba(59, 130, 246, 0.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#60A5FA",
                  flexShrink: 0,
                }}
              >
                <item.icon size={18} />
              </div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.08em", color: "#3B82F6" }}>
                  {item.phase}
                </div>
                <div style={{ fontSize: 13, color: "#F2F5F8", marginTop: 2 }}>
                  {item.text}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 10. AEO FAQ SECTION */}
      <section
        style={{
          maxWidth: 900,
          margin: "0 auto",
          padding: "80px 24px",
          borderTop: "1px solid #212836",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#3B82F6", marginBottom: 12 }}>
            FREQUENTLY ASKED QUESTIONS
          </div>
          <h2
            style={{
              fontSize: "clamp(24px, 3.5vw, 36px)",
              fontWeight: 700,
              color: "#F2F5F8",
              margin: 0,
            }}
          >
            Questions & Answers
          </h2>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {faqs.map((faq, idx) => {
            const isOpen = openFaq === idx;
            return (
              <div
                key={faq.q}
                style={{
                  border: "1px solid #212836",
                  borderRadius: 10,
                  background: "#10151C",
                  overflow: "hidden",
                }}
              >
                <button
                  type="button"
                  onClick={() => setOpenFaq(isOpen ? null : idx)}
                  style={{
                    width: "100%",
                    padding: "18px 20px",
                    textAlign: "left",
                    background: "none",
                    border: "none",
                    color: "#F2F5F8",
                    fontSize: 15,
                    fontWeight: 600,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    cursor: "pointer",
                  }}
                >
                  <span>{faq.q}</span>
                  <ChevronDown
                    size={18}
                    style={{
                      transform: isOpen ? "rotate(180deg)" : "rotate(0)",
                      transition: "transform 0.2s",
                      color: "#707A88",
                      flexShrink: 0,
                    }}
                  />
                </button>
                {isOpen && (
                  <div
                    style={{
                      padding: "0 20px 18px",
                      fontSize: 14,
                      lineHeight: 1.65,
                      color: "#A8B1BD",
                      borderTop: "1px solid #212836",
                      paddingTop: 12,
                    }}
                  >
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* 11. PRIVATE BETA CTA */}
      <section
        style={{
          maxWidth: 1000,
          margin: "0 auto 80px",
          padding: "64px 24px",
          background: "#10151C",
          border: "1px solid #212836",
          borderRadius: 20,
          textAlign: "center",
          boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(28px, 4.5vw, 42px)",
            fontWeight: 800,
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            color: "#F2F5F8",
            marginBottom: 16,
          }}
        >
          Build with AI. Keep control.
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.6,
            color: "#A8B1BD",
            maxWidth: 620,
            margin: "0 auto 36px",
          }}
        >
          SUTRA is currently available as a private beta for teams experimenting with real-world AI-assisted engineering workflows.
        </p>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <Link
            href="/register"
            className="btn primary"
            style={{
              padding: "14px 36px",
              borderRadius: 999,
              fontSize: 15,
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Join the Private Beta
          </Link>
          <div style={{ fontSize: 13, color: "#707A88" }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "#60A5FA", textDecoration: "underline", fontWeight: 500 }}>
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* 12. FOOTER */}
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
            <a href="#product" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              Product
            </a>
            <a href="#how-it-works" style={{ color: "#A8B1BD", textDecoration: "none" }}>
              How It Works
            </a>
            <Link href="/about" style={{ color: "#A8B1BD", textDecoration: "none" }}>
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
              Join the Private Beta
            </Link>
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
          <div>AI-Native Engineering Control Plane</div>
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
