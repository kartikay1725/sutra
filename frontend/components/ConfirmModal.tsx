"use client";

import React, { useEffect } from "react";
import * as I from "lucide-react";

export interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmTone?: "danger" | "warning" | "primary";
  loading?: boolean;
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  confirmTone = "danger",
  loading = false,
}: ConfirmModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, loading, onClose]);

  if (!isOpen) return null;

  const isDanger = confirmTone === "danger";
  const isWarning = confirmTone === "warning";

  const accentColor = isDanger
    ? "var(--red, #ef4444)"
    : isWarning
    ? "var(--amber, #f59e0b)"
    : "var(--cyan, #06b6d4)";

  const accentBg = isDanger
    ? "rgba(239, 68, 68, 0.12)"
    : isWarning
    ? "rgba(245, 158, 11, 0.12)"
    : "rgba(6, 182, 212, 0.12)";

  const accentBorder = isDanger
    ? "rgba(239, 68, 68, 0.28)"
    : isWarning
    ? "rgba(245, 158, 11, 0.28)"
    : "rgba(6, 182, 212, 0.28)";

  const confirmBtnBg = isDanger
    ? "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
    : isWarning
    ? "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
    : "linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)";

  return (
    <div
      className="modal-overlay"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.85)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
        boxSizing: "border-box",
        animation: "fadeIn 0.2s ease-out",
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !loading) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        style={{
          background: "linear-gradient(145deg, #141418 0%, #0D0D11 100%)",
          border: `1px solid ${accentBorder}`,
          borderRadius: 20,
          width: "100%",
          maxWidth: 460,
          boxShadow: `0 24px 64px rgba(0,0,0,0.7), 0 0 32px ${accentBg}`,
          padding: 24,
          boxSizing: "border-box",
          animation: "scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
          color: "var(--fg, #f3f4f6)",
        }}
      >
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: accentBg,
              border: `1px solid ${accentBorder}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              color: accentColor,
            }}
          >
            {isDanger ? (
              <I.AlertTriangle size={22} />
            ) : isWarning ? (
              <I.AlertCircle size={22} />
            ) : (
              <I.Info size={22} />
            )}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <h3
              id="confirm-dialog-title"
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "#ffffff",
                margin: "0 0 8px 0",
                lineHeight: 1.3,
                letterSpacing: "-0.01em",
              }}
            >
              {title}
            </h3>
            <div
              style={{
                fontSize: 14,
                lineHeight: 1.55,
                color: "rgba(255, 255, 255, 0.65)",
                wordBreak: "break-word",
              }}
            >
              {description}
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 12,
            marginTop: 24,
            paddingTop: 16,
            borderTop: "1px solid rgba(255, 255, 255, 0.06)",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            style={{
              padding: "10px 18px",
              borderRadius: 12,
              fontSize: 14,
              fontWeight: 600,
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              color: "rgba(255, 255, 255, 0.8)",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.background = "rgba(255, 255, 255, 0.09)";
            }}
            onMouseLeave={(e) => {
              if (!loading) e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)";
            }}
          >
            {cancelText}
          </button>

          <button
            type="button"
            onClick={() => void onConfirm()}
            disabled={loading}
            style={{
              padding: "10px 20px",
              borderRadius: 12,
              fontSize: 14,
              fontWeight: 600,
              background: confirmBtnBg,
              border: "none",
              color: "#ffffff",
              boxShadow: `0 4px 16px ${accentBg}`,
              cursor: loading ? "not-allowed" : "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              opacity: loading ? 0.7 : 1,
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.filter = "brightness(1.1)";
            }}
            onMouseLeave={(e) => {
              if (!loading) e.currentTarget.style.filter = "none";
            }}
          >
            {loading && <I.Loader2 size={16} className="spin" style={{ animation: "spin 1s linear infinite" }} />}
            {loading ? "Processing…" : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
