"use client";

import React, { useState, useEffect } from "react";
import { Search, Book, ChevronRight, ArrowLeft, ExternalLink, HelpCircle } from "lucide-react";
import { sections, DocSection } from "./content/data";
import { useRouter } from "next/navigation";
import { authService } from "@/lib/auth";

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("sutra-overview");
  const [searchQuery, setSearchQuery] = useState("");
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
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#090C10", overflow: "hidden", color: "#F2F5F8" }}>
      {/* Header bar with Back button */}
      <div
        style={{
          flexShrink: 0,
          height: 58,
          borderBottom: "1px solid #212836",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          background: "#10151C",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
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
            Back to App
          </button>
          <div style={{ fontWeight: 700, fontSize: 15, color: "#F2F5F8", display: "flex", alignItems: "center", gap: 8 }}>
            <Book size={17} style={{ color: "#3B82F6" }} />
            SUTRA Documentation & Guides
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

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Docs Sidebar */}
        <aside
          className="no-scrollbar"
          style={{
            width: 290,
            borderRight: "1px solid #212836",
            display: "flex",
            flexDirection: "column",
            background: "#10151C",
            flexShrink: 0,
          }}
        >
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

          <div className="no-scrollbar" style={{ flex: 1, overflowY: "auto", padding: "12px 0" }}>
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
                      onClick={() => setActiveSection(sec.id)}
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
        <main
          className="no-scrollbar"
          style={{
            flex: 1,
            padding: "40px 60px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 24,
            background: "#090C10",
          }}
        >
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
            <h1 style={{ fontSize: 30, fontWeight: 700, marginTop: 8, color: "#F2F5F8" }}>
              {activeDoc.title}
            </h1>
          </div>

          <div
            style={{
              fontSize: 14,
              lineHeight: 1.7,
              color: "#A8B1BD",
              maxWidth: 920,
            }}
          >
            {activeDoc.content}
          </div>
        </main>
      </div>
    </div>
  );
}
