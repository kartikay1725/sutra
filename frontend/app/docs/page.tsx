"use client";

import React, { useState, useEffect } from "react";
import { Search, Book, ChevronRight, ArrowLeft, ExternalLink, HelpCircle, Menu, X } from "lucide-react";
import { sections, DocSection } from "./content/data";
import { useRouter } from "next/navigation";
import { authService } from "@/lib/auth";

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("sutra-overview");
  const [searchQuery, setSearchQuery] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const router = useRouter();

  // Sync with hash on load
  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash && sections.some((s) => s.id === hash)) {
      setActiveSection(hash);
    }
  }, []);

  // Update hash when section changes
  useEffect(() => {
    window.location.hash = activeSection;
  }, [activeSection]);

  const filteredSections = sections.filter(
    (sec) =>
      sec.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sec.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeDoc = sections.find((sec) => sec.id === activeSection) || sections[0];

  return (
    <div className="docs-page">
      {/* Header bar with Back button and mobile drawer trigger */}
      <div className="docs-header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => setMobileSidebarOpen((prev) => !prev)}
            className="docs-mobile-menu-btn"
            aria-label="Toggle navigation menu"
          >
            {mobileSidebarOpen ? <X size={15} /> : <Menu size={15} />}
            <span>Sections</span>
          </button>

          <button
            onClick={() => {
              if (authService.isAuthenticated()) {
                router.push("/home");
              } else {
                router.push("/");
              }
            }}
            className="btn"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "#171D26",
              border: "1px solid #212836",
              color: "#F2F5F8",
              fontSize: 13,
              fontWeight: 500,
              padding: "6px 14px",
              borderRadius: 8,
              height: 34,
            }}
          >
            <ArrowLeft size={14} />
            Back
          </button>
          <div style={{ fontWeight: 700, fontSize: 15, color: "#F2F5F8", display: "flex", alignItems: "center", gap: 8 }}>
            <Book size={17} style={{ color: "#3B82F6" }} />
            <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              SUTRA Docs
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <a
            href="/"
            style={{
              fontSize: 13,
              color: "#A8B1BD",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            Home
          </a>
          <a
            href="/about"
            style={{
              fontSize: 13,
              color: "#A8B1BD",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            About
          </a>
        </div>
      </div>

      <div className="docs-body">
        {/* Mobile Backdrop */}
        <div
          className={`docs-sidebar-backdrop ${mobileSidebarOpen ? "open" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
        />

        {/* Docs Sidebar */}
        <aside className={`docs-sidebar ${mobileSidebarOpen ? "open" : ""}`}>
          <div style={{ padding: "16px 14px", borderBottom: "1px solid #212836" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#171D26",
                border: "1px solid #212836",
                borderRadius: 8,
                padding: "6px 10px",
              }}
            >
              <Search size={14} style={{ color: "#707A88" }} />
              <input
                type="text"
                placeholder="Search guides & API..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#F2F5F8",
                  fontSize: 13,
                  width: "100%",
                  outline: "none",
                }}
              />
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "12px 0" }}>
            {/* Categories */}
            {Array.from(new Set(filteredSections.map((s) => s.category))).map((cat) => (
              <div key={cat} style={{ marginBottom: 18 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "0 16px",
                    color: "#3B82F6",
                    letterSpacing: "0.08em",
                    marginBottom: 8,
                  }}
                >
                  {cat}
                </div>
                {filteredSections
                  .filter((s) => s.category === cat)
                  .map((sec) => (
                    <button
                      key={sec.id}
                      onClick={() => {
                        setActiveSection(sec.id);
                        setMobileSidebarOpen(false);
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        width: "100%",
                        border: "none",
                        padding: "8px 16px",
                        fontSize: 13,
                        textAlign: "left",
                        cursor: "pointer",
                        background: activeSection === sec.id ? "rgba(59, 130, 246, 0.12)" : "transparent",
                        color: activeSection === sec.id ? "#60A5FA" : "#A8B1BD",
                        borderLeft: activeSection === sec.id ? "3px solid #3B82F6" : "3px solid transparent",
                        fontWeight: activeSection === sec.id ? 600 : 400,
                        transition: "all 0.15s",
                      }}
                    >
                      <ChevronRight size={12} style={{ opacity: activeSection === sec.id ? 1 : 0.4 }} />
                      <span>{sec.title}</span>
                    </button>
                  ))}
              </div>
            ))}
            {filteredSections.length === 0 && (
              <div style={{ padding: 16, fontSize: 13, color: "#707A88", textAlign: "center" }}>
                No guide found matching your search.
              </div>
            )}
          </div>
        </aside>

        {/* Content Pane */}
        <main className="docs-content-pane">
          <div style={{ borderBottom: "1px solid #212836", paddingBottom: 20 }}>
            <div
              style={{
                fontSize: 12,
                color: "#3B82F6",
                textTransform: "uppercase",
                fontWeight: 700,
                letterSpacing: "0.08em",
              }}
            >
              {activeDoc.category}
            </div>
            <h1 style={{ fontSize: 28, fontWeight: 700, marginTop: 8, color: "#F2F5F8", wordBreak: "break-word" }}>
              {activeDoc.title}
            </h1>
          </div>

          <div
            style={{
              fontSize: 14,
              lineHeight: 1.7,
              color: "#A8B1BD",
              maxWidth: 920,
              width: "100%",
            }}
          >
            {activeDoc.content}
          </div>

          <footer
            style={{
              borderTop: "1px solid #212836",
              marginTop: 64,
              paddingTop: 28,
              paddingBottom: 28,
              fontSize: 12,
              color: "#707A88",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
              maxWidth: 920,
            }}
          >
            <div>© {new Date().getFullYear()} SUTRA. A Sudarshan Harness Product. All rights reserved.</div>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <span>Contact us at <a href="mailto:sutra@sudarshanai.com" style={{ color: "#60A5FA", textDecoration: "none" }}>sutra@sudarshanai.com</a></span>
              <span>•</span>
              <span>AI-Native Engineering Control Plane</span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
