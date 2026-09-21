'use client';

import React, { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle, ArrowLeft, ShieldAlert } from "lucide-react";

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
  let message = "Processing authorization callback...";
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
    title = "Authorization Granted";
    message = "An authorization code was successfully granted. Your MCP coding client will now complete the connection.";
    statusBadge = "Connected";
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0B0B0F radial-gradient(circle at 50% 25%, #181E28 0%, #0B0B0F 80%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif',
        color: "#F0F6FC",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "460px",
          background: "#111418",
          border: "1px solid #202632",
          borderRadius: "16px",
          padding: "36px 32px",
          boxShadow: "0 24px 64px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.04)",
          textAlign: "center",
        }}
      >
        {/* Brand Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "10px",
            marginBottom: "20px",
            fontSize: "18px",
            fontWeight: 800,
            letterSpacing: "-0.02em",
          }}
        >
          <img
            src="/icon.png"
            alt="SUTRA"
            width={32}
            height={32}
            style={{
              width: "32px",
              height: "32px",
              objectFit: "contain",
              borderRadius: "8px",
              boxShadow: "0 2px 8px rgba(0, 0, 0, 0.4)",
            }}
          />
          <span style={{ color: "#F0F6FC" }}>SUTRA</span>
        </div>

        {/* Status Icon */}
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: isError
              ? "rgba(249, 115, 22, 0.12)"
              : "rgba(59, 130, 246, 0.12)",
            border: `1px solid ${
              isError ? "rgba(249, 115, 22, 0.3)" : "rgba(59, 130, 246, 0.3)"
            }`,
            color: isError ? "#F97316" : "#60A5FA",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 20px auto",
          }}
        >
          {isCancelled ? (
            <XCircle size={28} />
          ) : isError ? (
            <ShieldAlert size={28} />
          ) : (
            <CheckCircle2 size={28} />
          )}
        </div>

        {/* Badge */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "3px 10px",
            borderRadius: "4px",
            fontSize: "11px",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: "12px",
            background: isError
              ? "rgba(249, 115, 22, 0.1)"
              : "rgba(59, 130, 246, 0.1)",
            border: `1px solid ${
              isError ? "rgba(249, 115, 22, 0.25)" : "rgba(59, 130, 246, 0.25)"
            }`,
            color: isError ? "#FB923C" : "#60A5FA",
          }}
        >
          <span
            style={{
              width: "5px",
              height: "5px",
              borderRadius: "50%",
              backgroundColor: "currentColor",
            }}
          />
          {statusBadge}
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: "22px",
            fontWeight: 700,
            marginBottom: "10px",
            letterSpacing: "-0.02em",
            color: "#F0F6FC",
          }}
        >
          {title}
        </h1>

        {/* Message */}
        <p
          style={{
            fontSize: "13.5px",
            color: "#8B949E",
            lineHeight: 1.6,
            marginBottom: "28px",
          }}
        >
          {message}
        </p>

        {/* Next step guidance */}
        <div
          style={{
            padding: "16px",
            borderRadius: "8px",
            background: "#161B22",
            border: "1px solid #202632",
            marginBottom: "24px",
            fontSize: "12.5px",
            color: "#C9D1D9",
            lineHeight: 1.5,
          }}
        >
          You can now safely close this browser tab and return to your IDE or terminal.
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
          <button
            type="button"
            onClick={() => window.close()}
            style={{
              padding: "9px 20px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 600,
              background: "#161B22",
              border: "1px solid #2D333B",
              color: "#C9D1D9",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = "#38414D";
              e.currentTarget.style.color = "#FFFFFF";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = "#2D333B";
              e.currentTarget.style.color = "#C9D1D9";
            }}
          >
            Close Tab
          </button>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "9px 20px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 600,
              background: "#F97316",
              border: "1px solid #EA580C",
              color: "#FFFFFF",
              textDecoration: "none",
              boxShadow: "0 2px 8px rgba(249, 115, 22, 0.25)",
              transition: "all 0.15s ease",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = "#FB8C24";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = "#F97316";
            }}
          >
            <ArrowLeft size={14} /> Return to SUTRA
          </Link>
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
            background: "#0B0B0F",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#8B949E",
          }}
        >
          Loading...
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}
