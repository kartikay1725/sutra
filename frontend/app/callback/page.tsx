'use client';

import React, { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle, ArrowLeft, ShieldAlert, Laptop } from "lucide-react";

function CallbackContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");
  const code = searchParams.get("code");
  const state = searchParams.get("state");

  const isCancelled = error === "access_denied";
  const isError = Boolean(error);
  const isSuccess = Boolean(code);

  let title = "Authorization Callback";
  let message = "Processing sovereign authorization callback...";
  let statusBadge = "MCP · OAuth 2.1";

  if (isCancelled) {
    title = "Authorization Cancelled";
    message = errorDescription || "You cancelled the authorization request. No repository or agent access was granted.";
    statusBadge = "Cancelled";
  } else if (isError) {
    title = "Authorization Failed";
    message = errorDescription || `OAuth error: ${error}`;
    statusBadge = "Error";
  } else if (isSuccess) {
    title = "Authorization Attested";
    message = "An authorization code was securely granted. Your MCP coding client has established sovereign session authority.";
    statusBadge = "Connected";
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "radial-gradient(ellipse at 50% 20%, rgba(249, 115, 22, 0.08) 0%, #0B0B0B 75%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        color: "var(--text-primary)",
      }}
    >
      <div className="bezel-shell" style={{ width: "100%", maxWidth: "480px" }}>
        <div
          className="bezel-core"
          style={{
            padding: "40px 32px",
            textAlign: "center",
            background: "linear-gradient(180deg, #131317 0%, #0D0D10 100%)",
            boxShadow: "0 24px 64px rgba(0, 0, 0, 0.7)",
          }}
        >
          {/* Brand Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "10px",
              marginBottom: "24px",
              fontSize: "18px",
              fontWeight: 800,
              letterSpacing: "0.04em",
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                overflow: "hidden",
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <img
                src="/icon.png"
                alt="SUTRA"
                width={24}
                height={24}
                style={{ width: "24px", height: "24px", objectFit: "contain" }}
              />
            </div>
            <span style={{ color: "#FFFFFF" }}>SUTRA</span>
          </div>

          {/* Status Icon with Ambient Halo */}
          <div
            style={{
              width: "64px",
              height: "64px",
              borderRadius: "20px",
              background: isError
                ? "rgba(239, 68, 68, 0.12)"
                : "rgba(249, 115, 22, 0.12)",
              border: `1px solid ${
                isError ? "rgba(239, 68, 68, 0.3)" : "rgba(249, 115, 22, 0.3)"
              }`,
              color: isError ? "#EF4444" : "var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 20px auto",
              boxShadow: isError
                ? "0 0 24px rgba(239, 68, 68, 0.2)"
                : "0 0 24px rgba(249, 115, 22, 0.2)",
            }}
          >
            {isCancelled ? (
              <XCircle size={30} />
            ) : isError ? (
              <ShieldAlert size={30} />
            ) : (
              <CheckCircle2 size={30} />
            )}
          </div>

          {/* Status Chip */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "7px",
              padding: "3px 10px",
              borderRadius: "5px",
              fontSize: "11px",
              fontFamily: "var(--font-mono, monospace)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "16px",
              background: isError
                ? "rgba(239, 68, 68, 0.08)"
                : "rgba(249, 115, 22, 0.08)",
              border: `1px solid ${
                isError ? "rgba(239, 68, 68, 0.22)" : "rgba(249, 115, 22, 0.22)"
              }`,
              color: isError ? "#EF4444" : "var(--accent)",
            }}
          >
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: "currentColor",
                boxShadow: isError ? "0 0 6px #EF4444" : "0 0 6px var(--accent)",
              }}
            />
            {statusBadge}
          </div>

          {/* Title */}
          <h1
            style={{
              fontSize: "24px",
              fontWeight: 700,
              marginBottom: "10px",
              letterSpacing: "-0.02em",
              color: "#FFFFFF",
            }}
          >
            {title}
          </h1>

          {/* Message */}
          <p
            style={{
              fontSize: "14px",
              color: "var(--text-secondary)",
              lineHeight: 1.6,
              marginBottom: "28px",
            }}
          >
            {message}
          </p>

          {/* Next step guidance */}
          <div
            className="input-recessed"
            style={{
              padding: "16px",
              marginBottom: "24px",
              fontSize: "13px",
              color: "var(--text-secondary)",
              lineHeight: 1.5,
              display: "flex",
              alignItems: "center",
              gap: "12px",
              textAlign: "left",
            }}
          >
            <Laptop size={18} style={{ color: "var(--accent)", flexShrink: 0 }} />
            <span>You can now safely return to your IDE or terminal. Session authority is active.</span>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => window.close()}
              className="btn-island-ghost"
              style={{
                padding: "10px 20px",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              Close Tab
            </button>
            <Link
              href="/"
              className="btn-island"
              style={{
                padding: "10px 18px",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              <span>Return to SUTRA</span>
              <span className="icon-pill">
                <ArrowLeft size={12} />
              </span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            minHeight: "100vh",
            background: "#0B0B0B",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-muted)",
          }}
        >
          <div className="spinner" style={{ margin: "0 auto" }}></div>
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}

