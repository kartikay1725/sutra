'use client';
import React, { useState } from "react";
import Link from "next/link";
import { Btn } from "./shell";
import { authService } from "../lib/auth";

function Mark() {
  return <div className="mark" />;
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authService.forgotPassword(email);
      setMessage(res.message || "If an account exists for this email, a password reset link has been sent.");
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || "Failed to process request. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth-card">
        <div className="auth-brand">
          <Mark />
          SUTRA
        </div>
        <div className="auth-title">Reset your password.</div>
        <div className="auth-sub">
          Enter your email address and we'll send you a recovery link.
        </div>

        {error && (
          <div className="error-banner" style={{ color: "var(--red)", marginBottom: 16 }}>
            {error}
          </div>
        )}

        {submitted ? (
          <div style={{ textAlign: "center", padding: "12px 0" }}>
            <div
              style={{
                color: "var(--green, #28a745)",
                fontSize: 14,
                marginBottom: 16,
                lineHeight: 1.5,
              }}
            >
              {message}
            </div>
            <p style={{ fontSize: 12, color: "#7f949f", marginBottom: 20 }}>
              Please check your spam or junk folder if you don't receive an email within a few minutes.
            </p>
            <Link href="/login" className="btn" style={{ width: "100%", justifyContent: "center", display: "inline-flex", textDecoration: "none" }}>
              Return to Sign In
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label className="label">Email Address</label>
              <input
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
              />
            </div>
            <Btn primary style={{ width: "100%" }} type="submit" disabled={loading || !email}>
              {loading ? "Sending link..." : "Send Reset Link"}
            </Btn>
            <div style={{ textAlign: "center", fontSize: 11, color: "#7f949f", marginTop: 14 }}>
              Remembered your password?{" "}
              <Link href="/login" className="auth-link">
                Sign in
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
