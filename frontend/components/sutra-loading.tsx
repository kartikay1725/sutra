"use client";

import React from "react";

export function SutraLoading({
  message,
  fullscreen = false,
}: {
  message?: string;
  quote?: boolean;
  fullscreen?: boolean;
}) {
  return (
    <div
      className={fullscreen ? "sutra-loading-fullscreen" : "sutra-loading-container"}
      role="status"
      aria-label="Loading SUTRA"
    >
      <div
        style={{
          width: "100%",
          maxWidth: 580,
          padding: "24px 28px",
          borderRadius: 12,
          border: "1px solid var(--line)",
          background: "var(--bg-subtle)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div className="skeleton" style={{ width: 140, height: 18, borderRadius: 4 }} />
          <div className="skeleton" style={{ width: 60, height: 16, borderRadius: 8 }} />
        </div>

        <div className="skeleton" style={{ width: "100%", height: 3, borderRadius: 2 }} />

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="skeleton" style={{ width: "85%", height: 14, borderRadius: 4 }} />
          <div className="skeleton" style={{ width: "65%", height: 14, borderRadius: 4 }} />
          <div className="skeleton" style={{ width: "40%", height: 14, borderRadius: 4 }} />
        </div>

        {message && (
          <div
            style={{
              fontSize: 13,
              color: "var(--muted)",
              marginTop: 4,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--cyan)",
                display: "inline-block",
                boxShadow: "0 0 6px var(--cyan)",
              }}
            />
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
