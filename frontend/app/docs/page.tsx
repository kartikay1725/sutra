"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, ArrowLeft, Menu, X, ChevronDown, Check, BookOpen, ExternalLink, ArrowRight } from "lucide-react";
import { sections } from "./content/data";
import { useRouter } from "next/navigation";
import { authService } from "@/lib/auth";
import Link from "next/link";

const HASH_ALIASES: Record<string, string> = {
  "sutra-overview": "getting-started",
  "overview": "getting-started",
  "engineering-workflow": "human-guide",
  "tasks": "human-guide",
  "changes": "human-guide",
  "prs": "human-guide",
  "mcp": "mcp-integration",
  "agent": "ai-agent-guide",
  "agents": "ai-agent-guide",
  "contract": "agent-contract",
  "security": "security-governance",
  "governance": "security-governance",
  "api": "api-reference",
};

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("getting-started");
  const [activeSubheading, setActiveSubheading] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [targetFilter, setTargetFilter] = useState<"all" | "agents" | "humans">("all");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Sync with hash on load & resolve aliases
  useEffect(() => {
    const rawHash = window.location.hash.replace("#", "");
    if (rawHash) {
      const resolved = HASH_ALIASES[rawHash] || rawHash;
      if (sections.some((s) => s.id === resolved)) {
        setActiveSection(resolved);
      }
    }
  }, []);

  // Update hash when section changes
  useEffect(() => {
    window.location.hash = activeSection;
    window.scrollTo({ top: 0, behavior: "smooth" });
    setActiveSubheading(null);
  }, [activeSection]);

  // Global Keyboard Shortcut (⌘K / Ctrl+K) to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
      if (e.key === "Escape") {
        searchInputRef.current?.blur();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const filteredSections = sections.filter(
    (sec) =>
      sec.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sec.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeDoc = sections.find((sec) => sec.id === activeSection) || sections[0];

  const handleTocClick = (id: string) => {
    setActiveSubheading(id);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  const categories = Array.from(new Set(sections.map((s) => s.category)));

  return (
    <div className="docs-page">
      {/* 1. Top Navigation Bar (Reddit-style clean light top navigation) */}
      <header className="docs-header">
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <Link 
            href="/" 
            style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: 10, 
              textDecoration: "none", 
              color: "#0F172A" 
            }}
          >
            <div 
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "rgba(249, 115, 22, 0.12)",
                border: "1px solid rgba(249, 115, 22, 0.35)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <img src="/icon.png" alt="SUTRA" style={{ width: 20, height: 20, objectFit: "contain" }} />
            </div>
            <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.02em", color: "#0F172A" }}>SUTRA</span>
          </Link>
        </div>

        {/* Center Links */}
        <nav style={{ display: "none", alignItems: "center", gap: 24 }} className="desktop-nav">
          <Link href="/docs" style={{ fontSize: 13.5, fontWeight: 700, color: "#EA580C", textDecoration: "none" }}>
            Documentation &amp; Rules
          </Link>
          <Link href="/support" style={{ fontSize: 13.5, fontWeight: 500, color: "#475569", textDecoration: "none" }}>
            Support
          </Link>
        </nav>

        {/* Right CTA Button (Reddit-style bold rounded button) */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => setMobileSidebarOpen((prev) => !prev)}
            className="docs-mobile-menu-btn"
            style={{ display: "none" }}
            aria-label="Toggle navigation menu"
          >
            {mobileSidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>

          <Link
            href="/login"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: "#FF4500",
              color: "#FFFFFF",
              fontSize: 13,
              fontWeight: 700,
              padding: "8px 22px",
              borderRadius: 999,
              textDecoration: "none",
              boxShadow: "0 2px 8px rgba(255, 69, 0, 0.35)",
              transition: "transform 150ms ease, background 150ms ease",
            }}
            className="btn-primary-hover"
          >
            Launch Console
          </Link>
        </div>
      </header>

      {/* 2. Bold Branded Hero Banner (Exact Reddit Rules Format with Mascot Card) */}
      <section className="docs-hero-banner">
        <div 
          style={{ 
            maxWidth: 1320, 
            margin: "0 auto", 
            display: "flex", 
            alignItems: "center", 
            gap: 26,
            flexWrap: "wrap"
          }}
        >
          {/* Mascot / Logo Card (White squircle container matching Reddit mascot card) */}
          <div 
            style={{
              width: 76,
              height: 76,
              borderRadius: 22,
              background: "#FFFFFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 12px 30px rgba(0, 0, 0, 0.22)",
              flexShrink: 0,
            }}
          >
            <img 
              src="/icon.png" 
              alt="SUTRA" 
              style={{ width: 48, height: 48, objectFit: "contain" }} 
            />
          </div>

          <div>
            <h1 
              style={{ 
                fontSize: "clamp(28px, 4.2vw, 44px)", 
                fontWeight: 900, 
                color: "#FFFFFF", 
                letterSpacing: "-0.03em", 
                margin: 0,
                lineHeight: 1.15
              }}
            >
              SUTRA Rules &amp; Governance
            </h1>
            <p 
              style={{ 
                margin: "8px 0 0", 
                fontSize: "clamp(14px, 1.8vw, 16px)", 
                color: "rgba(255, 255, 255, 0.95)", 
                fontWeight: 500,
                maxWidth: 720
              }}
            >
              Official specifications, agent boundary contracts, and engineering control plane documentation.
            </p>
          </div>
        </div>
      </section>

      {/* 3. Selector Pills Strip (Reddit Rules Filter Pills Format) */}
      <div className="docs-filter-bar">
        <div 
          style={{ 
            maxWidth: 1320, 
            margin: "0 auto", 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 14
          }}
        >
          {/* Filter Pills */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            {/* Category / Section Dropdown Pill */}
            <div style={{ position: "relative" }}>
              <select
                value={activeSection}
                onChange={(e) => setActiveSection(e.target.value)}
                style={{
                  appearance: "none",
                  background: "#FFFFFF",
                  border: "1px solid #D1D5DB",
                  color: "#0F172A",
                  padding: "8px 36px 8px 18px",
                  borderRadius: 999,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  outline: "none",
                  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.05)",
                }}
              >
                {sections.map((sec) => (
                  <option key={sec.id} value={sec.id} style={{ background: "#FFFFFF", color: "#0F172A" }}>
                    {sec.category}: {sec.title}
                  </option>
                ))}
              </select>
              <ChevronDown 
                size={14} 
                style={{ 
                  position: "absolute", 
                  right: 14, 
                  top: "50%", 
                  transform: "translateY(-50%)", 
                  pointerEvents: "none",
                  color: "#64748B"
                }} 
              />
            </div>

            {/* Target Audience Pill */}
            <div style={{ position: "relative" }}>
              <select
                value={targetFilter}
                onChange={(e: any) => setTargetFilter(e.target.value)}
                style={{
                  appearance: "none",
                  background: "#FFFFFF",
                  border: "1px solid #D1D5DB",
                  color: "#0F172A",
                  padding: "8px 36px 8px 18px",
                  borderRadius: 999,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  outline: "none",
                  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.05)",
                }}
              >
                <option value="all">Target: All Developers &amp; Agents</option>
                <option value="agents">Target: AI Autonomous Agents (MCP)</option>
                <option value="humans">Target: Human Reviewers &amp; Owners</option>
              </select>
              <ChevronDown 
                size={14} 
                style={{ 
                  position: "absolute", 
                  right: 14, 
                  top: "50%", 
                  transform: "translateY(-50%)", 
                  pointerEvents: "none",
                  color: "#64748B"
                }} 
              />
            </div>
          </div>

          {/* Quick Search Input */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0 14px",
              height: 38,
              width: 320,
              maxWidth: "100%",
              background: "#FFFFFF",
              border: "1px solid #D1D5DB",
              borderRadius: 999,
              boxShadow: "0 1px 2px rgba(0, 0, 0, 0.05)",
            }}
          >
            <Search size={14} style={{ color: "#64748B", flexShrink: 0 }} />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search guides &amp; rules..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: "transparent",
                border: "none",
                color: "#0F172A",
                fontSize: 13,
                width: "100%",
                outline: "none",
              }}
            />
            <kbd style={{ background: "#F1F5F9", border: "1px solid #E2E8F0", borderRadius: 4, padding: "2px 6px", fontSize: 10, color: "#64748B" }}>
              ⌘K
            </kbd>
          </div>
        </div>
      </div>

      {/* 4. Main Body: Reddit Rules Two-Column Layout */}
      <div className="docs-body">
        {/* Left Navigation (Reddit Rules Style Sidebar: Clean, spacious list with active orange accent) */}
        <aside className="docs-sidebar">
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {categories.map((cat) => {
              const catSections = filteredSections.filter((s) => s.category === cat);
              if (catSections.length === 0) return null;

              return (
                <div key={cat}>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#64748B",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      marginBottom: 8,
                      paddingLeft: 6,
                    }}
                  >
                    {cat}
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    {catSections.map((sec) => {
                      const isActive = activeSection === sec.id;
                      return (
                        <button
                          key={sec.id}
                          onClick={() => {
                            setActiveSection(sec.id);
                            setMobileSidebarOpen(false);
                          }}
                          style={{
                            background: isActive ? "rgba(255, 69, 0, 0.08)" : "transparent",
                            border: "none",
                            padding: "8px 12px 8px 10px",
                            textAlign: "left",
                            cursor: "pointer",
                            fontSize: isActive ? 14.5 : 14,
                            fontWeight: isActive ? 700 : 500,
                            color: isActive ? "#EA580C" : "#475569",
                            borderLeft: `3px solid ${isActive ? "#EA580C" : "transparent"}`,
                            borderRadius: "0 6px 6px 0",
                            transition: "all 120ms ease",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                          }}
                        >
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {sec.title}
                          </span>
                          {isActive && (
                            <ArrowRight size={13} style={{ color: "#EA580C", flexShrink: 0 }} />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Right Reading Pane: Clean Light High-Contrast Editorial Article */}
        <main className="docs-content-pane">
          <div className="docs-content-layout">
            <article className="docs-article">
              {/* Category Breadcrumb & Title */}
              <div style={{ borderBottom: "1px solid #E5E7EB", paddingBottom: 20, marginBottom: 28 }}>
                <div
                  style={{
                    fontSize: 11.5,
                    color: "#EA580C",
                    textTransform: "uppercase",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    fontFamily: "var(--font-mono, monospace)",
                    marginBottom: 8,
                  }}
                >
                  {activeDoc.category} // POLICY SPECIFICATION
                </div>
                <h2 
                  style={{ 
                    fontSize: "clamp(26px, 3.2vw, 36px)", 
                    fontWeight: 800, 
                    color: "#0F172A", 
                    letterSpacing: "-0.025em", 
                    margin: 0,
                    lineHeight: 1.2
                  }}
                >
                  {activeDoc.title}
                </h2>
              </div>

              {/* Documentation Content Canvas */}
              <div
                className="docs-prose"
                style={{
                  fontSize: 15,
                  lineHeight: 1.75,
                  color: "#334155",
                  width: "100%",
                }}
              >
                {activeDoc.content}
              </div>

              {/* Documentation Footer */}
              <footer
                style={{
                  borderTop: "1px solid #E5E7EB",
                  marginTop: 64,
                  paddingTop: 28,
                  paddingBottom: 28,
                  fontSize: 12.5,
                  color: "#64748B",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 16,
                }}
              >
                <div>© {new Date().getFullYear()} SUTRA. An AchintAI Product. All rights reserved.</div>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <span>Questions? <a href="mailto:sutra@sudarshanai.com" style={{ color: "#EA580C", textDecoration: "none", fontWeight: 600 }}>sutra@sudarshanai.com</a></span>
                  <span>•</span>
                  <span>AI-Native Engineering Control Plane</span>
                </div>
              </footer>
            </article>

            {/* Right-Side "On this page" TOC */}
            {activeDoc.toc && activeDoc.toc.length > 1 && (
              <aside className="docs-toc" aria-label="On this page navigation">
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: "#64748B",
                    marginBottom: 14,
                  }}
                >
                  On this page
                </div>
                <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {activeDoc.toc.map((item) => {
                    const isCurrent = activeSubheading === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleTocClick(item.id)}
                        style={{
                          background: "none",
                          border: "none",
                          padding: "3px 0",
                          fontSize: 12.5,
                          textAlign: "left",
                          cursor: "pointer",
                          color: isCurrent ? "#EA580C" : "#64748B",
                          fontWeight: isCurrent ? 700 : 400,
                          lineHeight: 1.45,
                          transition: "color 0.12s ease",
                        }}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </nav>
              </aside>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
