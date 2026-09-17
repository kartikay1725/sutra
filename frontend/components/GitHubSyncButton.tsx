"use client";

import React, { useState, useEffect, useRef } from "react";
import { GitBranch, RefreshCw, CheckCircle2, AlertTriangle, ExternalLink, ChevronDown } from "lucide-react";
import { integrationService, type GitHubStatus } from "@/lib/integrations";

interface GitHubSyncButtonProps {
  variant?: "button" | "compact" | "badge";
  onSynced?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export function GitHubSyncButton({
  variant = "button",
  onSynced,
  className,
  style,
}: GitHubSyncButtonProps) {
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isDebounced, setIsDebounced] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await integrationService.getGitHubStatus();
      setStatus(res);
    } catch (err: any) {
      setError(err?.message || "Failed to load GitHub status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadStatus();

    const handleOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const handleConnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const { redirect_url } = await integrationService.getGitHubConnectUrl();
      window.location.href = redirect_url;
    } catch (err: any) {
      setError(err?.message || "Failed to initiate GitHub connection");
      setBusy(false);
    }
  };

  const handleSync = async (force = false) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await integrationService.syncGitHub(force);
      if (result.status === "debounced") {
        setIsDebounced(true);
        const mins = Math.max(1, Math.ceil((result.cooldown_remaining_seconds || 300) / 60));
        setNotice(`Sync cooldown active (~${mins}m remaining). Use Force Sync to bypass.`);
      } else {
        setIsDebounced(false);
        setNotice("Repositories successfully synchronized with GitHub.");
        setTimeout(() => setNotice(null), 4000);
      }
      await loadStatus();
      onSynced?.();
      window.dispatchEvent(new CustomEvent("sutra:github-synced"));
    } catch (err: any) {
      setError("GitHub sync service is temporarily busy. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const isSyncing = busy || status?.sync_status === "in_progress";

  if (loading && !status) {
    return (
      <button
        type="button"
        disabled
        className={`btn ${className || ""}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          padding: "6px 12px",
          opacity: 0.6,
          ...style,
        }}
      >
        <RefreshCw size={13} className="spin" />
        <span>GitHub…</span>
      </button>
    );
  }

  // Not connected
  if (!status?.connected) {
    return (
      <button
        type="button"
        onClick={handleConnect}
        disabled={busy}
        className={`btn primary ${className || ""}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          fontWeight: 600,
          padding: variant === "compact" ? "5px 10px" : "6px 14px",
          borderRadius: 8,
          ...style,
        }}
        title="Connect your GitHub account to sync repositories"
      >
        <GitBranch size={13} />
        <span>{busy ? "Connecting…" : "Connect GitHub"}</span>
      </button>
    );
  }

  // Compact icon button for Topbar / Header
  if (variant === "compact") {
    return (
      <div ref={dropdownRef} style={{ position: "relative", display: "inline-flex", ...style }}>
        <button
          type="button"
          onClick={() => setShowDropdown(!showDropdown)}
          className={`btn ${className || ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            height: 34,
            padding: "0 10px",
            borderRadius: 8,
            background: isSyncing ? "rgba(34, 211, 238, 0.12)" : "rgba(255, 255, 255, 0.04)",
            border: `1px solid ${isSyncing ? "rgba(34, 211, 238, 0.3)" : "var(--line)"}`,
            color: isSyncing ? "var(--cyan)" : "var(--fg)",
            cursor: "pointer",
          }}
          title={`GitHub: @${status.account || "connected"}`}
        >
          <GitBranch size={13} color="var(--cyan)" />
          {isSyncing ? (
            <RefreshCw size={12} className="spin" />
          ) : (
            <span style={{ fontSize: 11, fontWeight: 500 }}>Sync</span>
          )}
          <ChevronDown size={11} style={{ opacity: 0.5 }} />
        </button>

        {showDropdown && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              right: 0,
              zIndex: 9999,
              width: 280,
              background: "linear-gradient(145deg, #141418 0%, #0D0D11 100%)",
              border: "1px solid var(--line)",
              borderRadius: 12,
              padding: 14,
              boxShadow: "0 16px 40px rgba(0,0,0,0.6)",
              animation: "fadeIn 0.15s ease",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--fg)" }}>
                GitHub Integration
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--green)",
                  background: "rgba(34, 197, 94, 0.12)",
                  padding: "2px 6px",
                  borderRadius: 4,
                  border: "1px solid rgba(34, 197, 94, 0.25)",
                }}
              >
                Connected
              </span>
            </div>

            <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>
              Account: <strong style={{ color: "var(--fg)" }}>@{status.account}</strong>
              <br />
              {status.repo_count} repositories synced
              {status.last_synced_at && (
                <div style={{ fontSize: 10, marginTop: 4, opacity: 0.8 }}>
                  Last synced: {new Date(status.last_synced_at).toLocaleTimeString()}
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => handleSync(false)}
                disabled={isSyncing}
                className="btn primary"
                style={{
                  flex: 1,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  padding: "6px 10px",
                }}
              >
                <RefreshCw size={11} className={isSyncing ? "spin" : ""} />
                {isSyncing ? "Syncing…" : "Sync Now"}
              </button>

              {isDebounced && (
                <button
                  type="button"
                  onClick={() => handleSync(true)}
                  disabled={isSyncing}
                  className="btn outline"
                  style={{ fontSize: 11, padding: "6px 8px" }}
                  title="Bypass cooldown and synchronize immediately"
                >
                  Force
                </button>
              )}
            </div>

            {notice && (
              <div style={{ fontSize: 11, color: "var(--cyan)", marginTop: 8 }}>
                {notice}
              </div>
            )}
            {error && (
              <div style={{ fontSize: 11, color: "var(--red)", marginTop: 8 }}>
                {error}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // Full Button (e.g. on Repositories page)
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, ...style }}>
      <button
        type="button"
        onClick={() => handleSync(false)}
        disabled={isSyncing}
        className={`btn ${className || ""}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          fontWeight: 600,
          padding: "6px 14px",
          borderRadius: 8,
          background: isSyncing ? "rgba(34, 211, 238, 0.12)" : "rgba(255, 255, 255, 0.04)",
          border: `1px solid ${isSyncing ? "rgba(34, 211, 238, 0.3)" : "var(--line)"}`,
          color: isSyncing ? "var(--cyan)" : "var(--fg)",
          cursor: isSyncing ? "wait" : "pointer",
        }}
        title={status.last_synced_at ? `Last synced: ${new Date(status.last_synced_at).toLocaleString()}` : "Synchronize repositories with GitHub"}
      >
        <RefreshCw size={13} className={isSyncing ? "spin" : ""} />
        <span>{isSyncing ? "Syncing GitHub…" : "Sync GitHub"}</span>
      </button>

      {isDebounced && (
        <button
          type="button"
          onClick={() => handleSync(true)}
          disabled={isSyncing}
          className="btn outline"
          style={{
            fontSize: 11,
            padding: "6px 10px",
            borderRadius: 8,
          }}
          title="Bypass cooldown and synchronize immediately"
        >
          Force Sync
        </button>
      )}

      {notice && (
        <span style={{ fontSize: 11, color: "var(--cyan)" }}>
          {notice}
        </span>
      )}
      {error && (
        <span style={{ fontSize: 11, color: "var(--red)" }}>
          {error}
        </span>
      )}
    </div>
  );
}
