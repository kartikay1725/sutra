"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, ArrowLeft, Menu, X, ChevronRight, Hash } from "lucide-react";
import { sections, DocSection } from "./content/data";
import { useRouter } from "next/navigation";
import { authService } from "@/lib/auth";

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

  return (
    <div className="docs-page">
      {/* Compact Top Header */}
      <header className="docs-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", background: "var(--surface-1)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={() => setMobileSidebarOpen((prev) => !prev)}
            className="docs-mobile-menu-btn"
            aria-label="Toggle navigation menu"
          >
            {mobileSidebarOpen ? <X size={14} /> : <Menu size={14} />}
            <span>Menu</span>
          </button>

          <button
            onClick={() => {
              if (authService.isAuthenticated()) {
                router.push("/home");
              } else {
                router.push("/");
              }
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: "transparent",
              border: "none",
              color: "#F0F6FC",
              fontSize: 14,
              fontWeight: 600,
              padding: "4px 8px",
              cursor: "pointer",
              borderRadius: 6,
              transition: "color 0.15s ease",
            }}
            title="Return to SUTRA app"
          >
            <ArrowLeft size={14} style={{ color: "#8B949E" }} />
            <span>SUTRA Docs</span>
          </button>
        </div>

        <nav style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <a
            href="/"
            style={{
              fontSize: 13,
              color: "#8B949E",
              textDecoration: "none",
              transition: "color 0.15s ease",
            }}
            className="hover:text-white"
          >
            Home
          </a>
          <a
            href="/about"
            style={{
              fontSize: 13,
              color: "#8B949E",
              textDecoration: "none",
              transition: "color 0.15s ease",
            }}
            className="hover:text-white"
          >
            About
          </a>
        </nav>
      </header>

      <div className="docs-body">
        {/* Mobile Backdrop */}
        <div
          className={`docs-sidebar-backdrop ${mobileSidebarOpen ? "open" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
        />

        {/* Left Navigation Sidebar (240-270px) */}
        <aside className={`docs-sidebar ${mobileSidebarOpen ? "open" : ""}`}>
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border-default)" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#0D1117",
                border: "1px solid #30363D",
                borderRadius: 6,
                padding: "6px 10px",
              }}
            >
              <Search size={13} style={{ color: "#8B949E", flexShrink: 0 }} />
              <input
                ref={searchInputRef}
                type="text"
                placeholder="Search guides & API..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#F0F6FC",
                  fontSize: 12.5,
                  width: "100%",
                  outline: "none",
                }}
              />
              <kbd className="docs-kbd">⌘K</kbd>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "12px 8px" }}>
            {/* Grouped Categories */}
            {Array.from(new Set(filteredSections.map((s) => s.category))).map((cat) => (
              <div key={cat} style={{ marginBottom: 16 }}>
                <div
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "0 10px",
                    color: "#8B949E",
                    letterSpacing: "0.06em",
                    marginBottom: 4,
                  }}
                >
                  {cat}
                </div>
                {filteredSections
                  .filter((s) => s.category === cat)
                  .map((sec) => {
                    const isActive = activeSection === sec.id;
                    return (
                      <button
                        key={sec.id}
                        onClick={() => {
                          setActiveSection(sec.id);
                          setMobileSidebarOpen(false);
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          width: "100%",
                          border: "none",
                          borderRadius: 6,
                          padding: "7px 10px",
                          fontSize: 12.5,
                          textAlign: "left",
                          cursor: "pointer",
                          background: isActive ? "rgba(249, 115, 22, 0.08)" : "transparent",
                          color: isActive ? "#F0F6FC" : "#8B949E",
                          fontWeight: isActive ? 600 : 400,
                          transition: "all 0.12s ease",
                          marginBottom: 2,
                        }}
                      >
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {sec.title}
                        </span>
                        {isActive && (
                          <span style={{ width: 4, height: 4, borderRadius: "50%", background: "#F97316", flexShrink: 0 }} />
                        )}
                      </button>
                    );
                  })}
              </div>
            ))}
            {filteredSections.length === 0 && (
              <div style={{ padding: "16px 12px", fontSize: 12, color: "#8B949E", textAlign: "center" }}>
                No guide found matching &quot;{searchQuery}&quot;.
              </div>
            )}
          </div>
        </aside>

        {/* Content Pane (Center Reading Column + Sticky Right TOC) */}
        <main className="docs-content-pane">
          <div className="docs-content-layout">
            {/* Center Article (760-900px max width) */}
            <article className="docs-article">
              <div style={{ borderBottom: "1px solid var(--border-default)", paddingBottom: 16, marginBottom: 24 }}>
                <div
                  style={{
                    fontSize: 11,
                    color: "#F97316",
                    textTransform: "uppercase",
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                  }}
                >
                  {activeDoc.category}
                </div>
                <h1 style={{ fontSize: 26, fontWeight: 700, marginTop: 6, color: "#F0F6FC", letterSpacing: "-0.02em", wordBreak: "break-word" }}>
                  {activeDoc.title}
                </h1>
              </div>

              {/* Direct Canvas Text - Minimal Container Overload */}
              <div
                style={{
                  fontSize: 13.5,
                  lineHeight: 1.7,
                  color: "#C9D1D9",
                  width: "100%",
                }}
              >
                {activeDoc.content}
              </div>

              {/* Documentation Footer */}
              <footer
                style={{
                  borderTop: "1px solid var(--border-default)",
                  marginTop: 64,
                  paddingTop: 24,
                  paddingBottom: 24,
                  fontSize: 11.5,
                  color: "#8B949E",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 12,
                }}
              >
                <div>© {new Date().getFullYear()} SUTRA. An AchintAI Product. All rights reserved.</div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span>Contact: <a href="mailto:sutra@sudarshanai.com" style={{ color: "#58A6FF", textDecoration: "none" }}>sutra@sudarshanai.com</a></span>
                  <span>•</span>
                  <span>AI-Native Engineering Control Plane</span>
                </div>
              </footer>
            </article>

            {/* Right-Side "On this page" TOC (180-220px) */}
            {activeDoc.toc && activeDoc.toc.length > 1 && (
              <aside className="docs-toc" aria-label="On this page navigation">
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "#8B949E",
                    marginBottom: 12,
                  }}
                >
                  On this page
                </div>
                <nav style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {activeDoc.toc.map((item) => {
                    const isCurrent = activeSubheading === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleTocClick(item.id)}
                        style={{
                          background: "none",
                          border: "none",
                          padding: "4px 0",
                          fontSize: 12,
                          textAlign: "left",
                          cursor: "pointer",
                          color: isCurrent ? "#F97316" : "#8B949E",
                          fontWeight: isCurrent ? 600 : 400,
                          lineHeight: 1.4,
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

