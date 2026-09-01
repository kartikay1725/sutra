'use client';
import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Btn } from "./shell";
import { authService } from "../lib/auth";

function Mark() {
  return <div className="mark" />;
}

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const email = searchParams.get("email") || "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!token || !email) {
      setError("Invalid password reset link. Missing token or email.");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match. Please re-enter.");
      return;
    }

    setLoading(true);
    try {
      await authService.resetPassword(token, email, newPassword);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Failed to reset password. The link may have expired or already been used.");
    } finally {
      setLoading(false);
    }
  };

  if (!token || !email) {
    return (
      <div className="auth">
        <div className="auth-card">
          <div className="auth-brand">
            <Mark />
            SUTRA
          </div>
          <div className="auth-title">Invalid Reset Link</div>
          <div className="auth-sub">
            This password reset link is invalid or incomplete.
          </div>
          <div style={{ textAlign: "center", marginTop: 20 }}>
            <Link href="/forgot-password" className="btn primary" style={{ width: "100%", justifyContent: "center", display: "inline-flex", textDecoration: "none" }}>
              Request New Reset Link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth">
      <div className="auth-card">
        <div className="auth-brand">
          <Mark />
          SUTRA
        </div>
        <div className="auth-title">Set new password.</div>
        <div className="auth-sub">
          Please enter your new password for {email}.
        </div>

        {error && (
          <div className="error-banner" style={{ color: "var(--red)", marginBottom: 16 }}>
            {error}
          </div>
        )}

        {success ? (
          <div style={{ textAlign: "center", padding: "12px 0" }}>
            <div
              style={{
                color: "var(--green, #28a745)",
                fontSize: 14,
                marginBottom: 16,
                lineHeight: 1.5,
              }}
            >
              Password successfully reset!
            </div>
            <p style={{ fontSize: 12, color: "#7f949f", marginBottom: 20 }}>
              All existing sessions have been invalidated. You can now sign in with your new password.
            </p>
            <Link href="/login" className="btn primary" style={{ width: "100%", justifyContent: "center", display: "inline-flex", textDecoration: "none" }}>
              Sign In
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label className="label">New Password</label>
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                minLength={8}
                required
              />
            </div>
            <div className="field">
              <label className="label">Confirm New Password</label>
              <input
                className="input"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your new password"
                minLength={8}
                required
              />
            </div>
            <Btn primary style={{ width: "100%" }} type="submit" disabled={loading || !newPassword || !confirmPassword}>
              {loading ? "Resetting password..." : "Reset Password"}
            </Btn>
            <div style={{ textAlign: "center", fontSize: 11, color: "#7f949f", marginTop: 14 }}>
              <Link href="/login" className="auth-link">
                Back to Sign In
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export function ResetPassword() {
  return (
    <Suspense fallback={<div className="auth"><div className="auth-card" style={{ textAlign: "center" }}>Loading...</div></div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
