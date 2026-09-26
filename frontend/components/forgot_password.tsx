'use client';
import React, { useState } from "react";
import Link from "next/link";
import { authService } from "../lib/auth";
import { KeyRound, ArrowRight, CheckCircle2, ShieldCheck, Mail, BookOpen } from "lucide-react";

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
      setMessage(res.message || "If an account exists for this email, a password recovery link has been dispatched.");
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || "Failed to process request. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      style={{
        height: "100vh",
        maxHeight: "100vh",
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "radial-gradient(circle at 50% 20%, rgba(249, 115, 22, 0.05) 0%, #0A0A0E 70%)",
        padding: "24px 20px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div style={{ width: "100%", maxWidth: 480 }}>
        {/* Brand header */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Link 
            href="/" 
            style={{ 
              display: "inline-flex", 
              alignItems: "center", 
              gap: 10, 
              textDecoration: "none", 
              color: "inherit",
              marginBottom: 16,
            }}
          >
            <div 
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: "linear-gradient(135deg, rgba(249, 115, 22, 0.18) 0%, rgba(249, 115, 22, 0.05) 100%)",
                border: "1px solid rgba(249, 115, 22, 0.3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <img src="/icon.png" alt="SUTRA" style={{ width: 22, height: 22, objectFit: "contain" }} />
            </div>
            <span style={{ fontSize: 18, fontWeight: 800, color: "#F8FAFC" }}>SUTRA</span>
          </Link>
          <div 
            style={{
              fontSize: 11,
              fontFamily: "var(--font-mono, monospace)",
              fontWeight: 600,
              color: "var(--accent, #F97316)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            CREDENTIAL RECOVERY
          </div>
        </div>

        {/* Double-Bezel Frame */}
        <div className="bezel-shell" style={{ width: "100%" }}>
          <div className="bezel-core" style={{ padding: "36px 32px" }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: "#F8FAFC", marginBottom: 6, textAlign: "center" }}>
              Reset your password
            </h2>
            <p style={{ fontSize: 13, color: "#94A3B8", textAlign: "center", marginBottom: 24, lineHeight: 1.5 }}>
              Enter your registered email address and we'll dispatch an authorization recovery link.
            </p>

            {error && (
              <div 
                style={{
                  color: "#F87171",
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid rgba(239, 68, 68, 0.25)",
                  padding: "10px 14px",
                  borderRadius: 8,
                  fontSize: 13,
                  marginBottom: 18,
                }}
              >
                {error}
              </div>
            )}

            {submitted ? (
              <div style={{ textAlign: "center" }}>
                <div 
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    background: "rgba(34, 197, 94, 0.12)",
                    border: "1px solid rgba(34, 197, 94, 0.3)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#22C55E",
                    margin: "0 auto 16px",
                  }}
                >
                  <CheckCircle2 size={22} />
                </div>
                <div style={{ color: "#F8FAFC", fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
                  Recovery Link Dispatched
                </div>
                <div style={{ color: "#94A3B8", fontSize: 13, lineHeight: 1.5, marginBottom: 24 }}>
                  {message}
                </div>
                <Link 
                  href="/login" 
                  className="btn-island" 
                  style={{ width: "100%", justifyContent: "center", textDecoration: "none" }}
                >
                  <span>Return to Sign In</span>
                  <span className="icon-pill">
                    <ArrowRight size={13} />
                  </span>
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: 22 }}>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                    Work Email Address
                  </label>
                  <input
                    className="input-recessed"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="example@mail.com"
                    required
                    style={{ width: "100%" }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !email}
                  className="btn-island"
                  style={{ width: "100%", justifyContent: "center", marginBottom: 16, opacity: (loading || !email) ? 0.6 : 1 }}
                >
                  <span>{loading ? "Dispatching..." : "Send Recovery Link"}</span>
                  <span className="icon-pill">
                    <ArrowRight size={13} />
                  </span>
                </button>

                <div style={{ textAlign: "center", fontSize: 13, color: "#94A3B8" }}>
                  Remembered your password?{" "}
                  <Link 
                    href="/login" 
                    style={{ 
                      color: "#F8FAFC", 
                      fontWeight: 600, 
                      textDecoration: "none",
                      borderBottom: "1px solid rgba(255, 255, 255, 0.3)" 
                    }}
                  >
                    Sign in
                  </Link>
                </div>
              </form>
            )}
          </div>
        </div>

        <div style={{ textAlign: "center", marginTop: 20, fontSize: 12, color: "#64748B" }}>
          SUTRA Identity Gateway • Zero-Trust Auth
        </div>
      </div>
    </div>
  );
}
