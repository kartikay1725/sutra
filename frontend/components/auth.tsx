'use client';
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authService } from "../lib/auth";
import { 
  ShieldCheck, 
  GitCommit, 
  Lock, 
  ArrowRight, 
  CheckCircle2, 
  Terminal, 
  Mail, 
  Layers,
  BookOpen
} from "lucide-react";

function SutraBrand() {
  return (
    <Link 
      href="/" 
      style={{ 
        display: "inline-flex", 
        alignItems: "center", 
        gap: 12, 
        textDecoration: "none",
        color: "inherit"
      }}
    >
      <div 
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: "linear-gradient(135deg, rgba(249, 115, 22, 0.2) 0%, rgba(249, 115, 22, 0.05) 100%)",
          border: "1px solid rgba(249, 115, 22, 0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 0 16px rgba(249, 115, 22, 0.15)"
        }}
      >
        <img
          src="/icon.png"
          alt="SUTRA"
          style={{
            width: 22,
            height: 22,
            objectFit: "contain",
          }}
        />
      </div>
      <div>
        <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.02em", color: "#F8FAFC" }}>
          SUTRA
        </span>
        <span 
          style={{ 
            display: "block", 
            fontSize: 10, 
            fontFamily: "var(--font-mono, monospace)", 
            color: "var(--accent, #F97316)", 
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Control Plane
        </span>
      </div>
    </Link>
  );
}

function CompactFeature({ icon: Icon, title, desc }: { icon: any; title: string; desc: string }) {
  return (
    <div 
      className="card-haptic"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "12px 14px",
        borderRadius: 10,
        background: "rgba(255, 255, 255, 0.02)",
        border: "1px solid rgba(255, 255, 255, 0.06)",
        backdropFilter: "blur(6px)",
      }}
    >
      <div 
        style={{
          width: 28,
          height: 28,
          borderRadius: 8,
          background: "rgba(249, 115, 22, 0.12)",
          border: "1px solid rgba(249, 115, 22, 0.25)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--accent, #F97316)",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        <Icon size={15} />
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#F1F5F9", marginBottom: 2 }}>
          {title}
        </div>
        <div style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.45 }}>
          {desc}
        </div>
      </div>
    </div>
  );
}

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState("");
  const [otpSuccess, setOtpSuccess] = useState("");
  const [cooldown, setCooldown] = useState(0);

  const router = useRouter();

  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authService.login(username, password);
      router.push("/home");
    } catch (err: any) {
      const msg = err.message || "Invalid credentials. Please try again.";
      setError(msg);
      if (msg.toLowerCase().includes("verify your email")) {
        setUnverifiedEmail(username.includes("@") ? username : "");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!unverifiedEmail) return;
    setOtpError("");
    setOtpLoading(true);
    try {
      await authService.verifyEmail(unverifiedEmail, otp);
      router.push("/home");
    } catch (err: any) {
      setOtpError(err.message || "Invalid verification code. Please try again.");
    } finally {
      setOtpLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (!unverifiedEmail || cooldown > 0) return;
    setOtpError("");
    setOtpSuccess("");
    try {
      const res = await authService.resendOtp(unverifiedEmail);
      setOtpSuccess(res.message || "Verification code resent.");
      setCooldown(60);
    } catch (err: any) {
      setOtpError(err.message || "Failed to resend code.");
    }
  };

  return (
    <div className="auth-grid-layout">
      {/* Subtle background ambient light */}
      <div 
        style={{
          position: "absolute",
          top: -80,
          right: -80,
          width: 450,
          height: 450,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(249, 115, 22, 0.08) 0%, transparent 70%)",
          pointerEvents: "none",
          filter: "blur(60px)",
        }}
      />

      {/* Left Column: Showcase */}
      <div 
        className="auth-sidebar-pane"
        style={{
          padding: "clamp(24px, 4vh, 48px) clamp(28px, 4vw, 56px)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          borderRight: "1px solid rgba(255, 255, 255, 0.06)",
          position: "relative",
          zIndex: 2,
          overflow: "hidden",
        }}
      >
        <div>
          <div style={{ marginBottom: "clamp(16px, 2.5vh, 28px)" }}>
            <SutraBrand />
          </div>

          <div 
            style={{
              fontSize: 11,
              fontFamily: "var(--font-mono, monospace)",
              fontWeight: 600,
              color: "var(--accent, #F97316)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 10,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#F97316", boxShadow: "0 0 8px #F97316" }} />
            Zero-Trust Agent Execution
          </div>

          <h1 
            style={{
              fontSize: "clamp(24px, 2.6vw, 34px)",
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: "-0.03em",
              color: "#F8FAFC",
              marginBottom: 12,
            }}
          >
            Safe autonomous engineering, from task to merge.
          </h1>

          <p style={{ fontSize: 14, color: "#94A3B8", lineHeight: 1.55, maxWidth: 480, marginBottom: "clamp(16px, 2.5vh, 26px)" }}>
            Sign in to govern autonomous coding agents with isolated sandboxes, cryptographic commit provenance, and mandatory human review gates.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 480 }}>
            <CompactFeature 
              icon={ShieldCheck} 
              title="Isolated Execution Workspaces" 
              desc="Agents run in short-lived environments without direct write permissions to main branches."
            />
            <CompactFeature 
              icon={GitCommit} 
              title="Cryptographic Commit Provenance" 
              desc="Every commit is digitally signed with verifiable agent identity, prompt metadata, and test output."
            />
            <CompactFeature 
              icon={Lock} 
              title="Mandatory Human Review Gate" 
              desc="Server-side kernel blocks agents from approving or merging code without human sign-off."
            />
          </div>
        </div>
      </div>

      {/* Right Column: Console Form */}
      <div 
        style={{
          padding: "clamp(20px, 3vh, 40px) clamp(24px, 3vw, 48px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          zIndex: 2,
          overflow: "hidden",
        }}
      >
        <div style={{ width: "100%", maxWidth: 480 }}>
          {/* Double-Bezel Frame */}
          <div className="bezel-shell" style={{ width: "100%" }}>
            <div className="bezel-core" style={{ padding: "clamp(24px, 3.5vh, 36px) clamp(24px, 3vw, 36px)" }}>
              {unverifiedEmail !== null ? (
                <>
                  <div style={{ textAlign: "center", marginBottom: 20 }}>
                    <div 
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: 12,
                        background: "rgba(249, 115, 22, 0.12)",
                        border: "1px solid rgba(249, 115, 22, 0.3)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "var(--accent, #F97316)",
                        margin: "0 auto 12px",
                      }}
                    >
                      <Mail size={20} />
                    </div>
                    <h2 style={{ fontSize: 22, fontWeight: 700, color: "#F8FAFC", marginBottom: 6 }}>
                      Verify your email
                    </h2>
                    <p style={{ fontSize: 13, color: "#94A3B8", lineHeight: 1.45 }}>
                      Enter the 6-digit confirmation code sent to your inbox.
                    </p>
                  </div>

                  {otpError && (
                    <div 
                      style={{
                        color: "#F87171",
                        background: "rgba(239, 68, 68, 0.1)",
                        border: "1px solid rgba(239, 68, 68, 0.25)",
                        padding: "10px 14px",
                        borderRadius: 8,
                        fontSize: 13,
                        marginBottom: 16,
                      }}
                    >
                      {otpError}
                    </div>
                  )}

                  {otpSuccess && (
                    <div 
                      style={{
                        color: "#4ADE80",
                        background: "rgba(34, 197, 94, 0.1)",
                        border: "1px solid rgba(34, 197, 94, 0.25)",
                        padding: "10px 14px",
                        borderRadius: 8,
                        fontSize: 13,
                        marginBottom: 16,
                      }}
                    >
                      {otpSuccess}
                    </div>
                  )}

                  <form onSubmit={handleVerifyOtp}>
                    {!unverifiedEmail && (
                      <div style={{ marginBottom: 16 }}>
                        <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                          Registered Email Address
                        </label>
                        <input
                          className="input-recessed"
                          type="email"
                          value={unverifiedEmail || ""}
                          onChange={(e) => setUnverifiedEmail(e.target.value)}
                          placeholder="example@mail.com"
                          required
                        />
                      </div>
                    )}

                    <div style={{ marginBottom: 20 }}>
                      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                        Verification Code
                      </label>
                      <input
                        className="input-recessed"
                        value={otp}
                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                        placeholder="••••••"
                        maxLength={6}
                        required
                        style={{
                          textAlign: "center",
                          fontSize: 20,
                          letterSpacing: "0.3em",
                          fontFamily: "var(--font-mono, monospace)",
                          fontWeight: 700,
                        }}
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={otpLoading || otp.length !== 6}
                      className="btn-island"
                      style={{ 
                        width: "100%", 
                        height: 46, 
                        justifyContent: "center", 
                        marginBottom: 10, 
                        fontSize: 14.5,
                        opacity: (otpLoading || otp.length !== 6) ? 0.6 : 1 
                      }}
                    >
                      <span>{otpLoading ? "Verifying..." : "Verify & Launch Console"}</span>
                      <span className="icon-pill">
                        <ArrowRight size={13} />
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={cooldown > 0 || !unverifiedEmail}
                      className="btn-island-ghost"
                      style={{ width: "100%", height: 42, justifyContent: "center", fontSize: 13.5 }}
                    >
                      <span>{cooldown > 0 ? `Resend Code (${cooldown}s)` : "Resend Code"}</span>
                    </button>
                  </form>

                  <div style={{ textAlign: "center", marginTop: 16 }}>
                    <button
                      type="button"
                      onClick={() => {
                        setUnverifiedEmail(null);
                        setError("");
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#94A3B8",
                        fontSize: 12.5,
                        cursor: "pointer",
                        textDecoration: "underline",
                      }}
                    >
                      Back to Sign In
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ marginBottom: "clamp(18px, 2.5vh, 24px)" }}>
                    <div 
                      style={{
                        fontSize: 11,
                        fontFamily: "var(--font-mono, monospace)",
                        fontWeight: 600,
                        color: "var(--accent, #F97316)",
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        marginBottom: 6,
                      }}
                    >
                      ENGINEERING CONSOLE
                    </div>
                    <h2 style={{ fontSize: "clamp(22px, 2.2vw, 25px)", fontWeight: 800, color: "#F8FAFC", letterSpacing: "-0.02em", marginBottom: 6 }}>
                      Sign In to SUTRA
                    </h2>
                    <p style={{ fontSize: 13, color: "#94A3B8" }}>
                      Authenticate with your organization credentials.
                    </p>
                  </div>

                  {error && (
                    <div 
                      style={{
                        color: "#F87171",
                        background: "rgba(239, 68, 68, 0.1)",
                        border: "1px solid rgba(239, 68, 68, 0.25)",
                        padding: "10px 14px",
                        borderRadius: 8,
                        fontSize: 13,
                        marginBottom: 16,
                        lineHeight: 1.4,
                      }}
                    >
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleLogin}>
                    <div style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                        Email or Username
                      </label>
                      <input
                        className="input-recessed"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="example@mail.com"
                        required
                        autoComplete="username"
                      />
                    </div>

                    <div style={{ marginBottom: 20 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <label style={{ fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", margin: 0 }}>
                          Password
                        </label>
                        <Link 
                          href="/forgot-password" 
                          style={{ 
                            fontSize: 12, 
                            color: "var(--accent, #F97316)", 
                            textDecoration: "none",
                            fontWeight: 500
                          }}
                        >
                          Forgot password?
                        </Link>
                      </div>
                      <input
                        className="input-recessed"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Password"
                        required
                        autoComplete="current-password"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="btn-island"
                      style={{ 
                        width: "100%", 
                        height: 46, 
                        justifyContent: "center", 
                        marginBottom: 14, 
                        fontSize: 14.5,
                        fontWeight: 600,
                        opacity: loading ? 0.7 : 1 
                      }}
                    >
                      <span>{loading ? "Authenticating Session..." : "Sign In to Console"}</span>
                      <span className="icon-pill">
                        <ArrowRight size={13} />
                      </span>
                    </button>
                  </form>

                  {error.toLowerCase().includes("verify your email") && (
                    <div style={{ textAlign: "center", marginTop: 4, marginBottom: 12 }}>
                      <button
                        type="button"
                        onClick={() => setUnverifiedEmail(username.includes("@") ? username : "")}
                        style={{ 
                          background: "none", 
                          border: "none", 
                          fontSize: 12.5, 
                          color: "var(--accent, #F97316)", 
                          cursor: "pointer", 
                          textDecoration: "underline" 
                        }}
                      >
                        Enter verification code / Resend code
                      </button>
                    </div>
                  )}

                  <div 
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      margin: "18px 0 16px",
                    }}
                  >
                    <div style={{ flex: 1, height: 1, background: "rgba(255, 255, 255, 0.08)" }} />
                    <span style={{ fontSize: 10.5, fontFamily: "var(--font-mono, monospace)", color: "#64748B", textTransform: "uppercase" }}>
                      ENTERPRISE ACCESS
                    </span>
                    <div style={{ flex: 1, height: 1, background: "rgba(255, 255, 255, 0.08)" }} />
                  </div>

                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 10,
                      background: "rgba(255, 255, 255, 0.02)",
                      border: "1px solid rgba(255, 255, 255, 0.07)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: 12.5,
                      color: "#94A3B8",
                      marginBottom: 18,
                    }}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <Lock size={13} style={{ color: "#64748B" }} />
                      Single Sign-On (SAML / OIDC)
                    </span>
                    <span 
                      style={{ 
                        fontSize: 10, 
                        fontFamily: "var(--font-mono, monospace)", 
                        padding: "2px 6px", 
                        borderRadius: 4, 
                        background: "rgba(255, 255, 255, 0.07)", 
                        color: "#94A3B8",
                        fontWeight: 600
                      }}
                    >
                      ENTERPRISE
                    </span>
                  </div>

                  <div style={{ textAlign: "center", fontSize: 13, color: "#94A3B8" }}>
                    New to SUTRA?{" "}
                    <Link 
                      href="/signup" 
                      style={{ 
                        color: "#F8FAFC", 
                        fontWeight: 600, 
                        textDecoration: "none",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.3)" 
                      }}
                    >
                      Create an account
                    </Link>
                  </div>
                </>
              )}
            </div>
          </div>

          <div style={{ textAlign: "center", marginTop: 16, fontSize: 12, color: "#64748B" }}>
            <Link 
              href="/docs#human-quickstart" 
              style={{ 
                color: "#94A3B8", 
                textDecoration: "none", 
                display: "inline-flex", 
                alignItems: "center", 
                gap: 5 
              }}
            >
              <BookOpen size={13} />
              Read Quickstart &amp; Architecture Guide
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Signup() {
  const [step, setStep] = useState<"form" | "otp">("form");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");

  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const router = useRouter();

  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authService.register(username, email, password);
      setSuccessMsg(res.message || "Verification code sent to your email.");
      setStep("otp");
      setCooldown(60);
    } catch (err: any) {
      setError(err.message || "Failed to create account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authService.verifyEmail(email, otp);
      router.push("/home");
    } catch (err: any) {
      setError(err.message || "Invalid verification code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (cooldown > 0) return;
    setError("");
    try {
      const res = await authService.resendOtp(email);
      setSuccessMsg(res.message || "Verification code resent.");
      setCooldown(60);
    } catch (err: any) {
      setError(err.message || "Failed to resend code.");
    }
  };

  return (
    <div className="auth-grid-layout">
      {/* Background ambient light */}
      <div 
        style={{
          position: "absolute",
          top: -80,
          left: -80,
          width: 450,
          height: 450,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(249, 115, 22, 0.08) 0%, transparent 70%)",
          pointerEvents: "none",
          filter: "blur(60px)",
        }}
      />

      {/* Left Column: Architecture Showcase */}
      <div 
        className="auth-sidebar-pane"
        style={{
          padding: "clamp(24px, 4vh, 48px) clamp(28px, 4vw, 56px)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          borderRight: "1px solid rgba(255, 255, 255, 0.06)",
          position: "relative",
          zIndex: 2,
          overflow: "hidden",
        }}
      >
        <div>
          <div style={{ marginBottom: "clamp(16px, 2.5vh, 28px)" }}>
            <SutraBrand />
          </div>

          <div 
            style={{
              fontSize: 11,
              fontFamily: "var(--font-mono, monospace)",
              fontWeight: 600,
              color: "var(--accent, #F97316)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 10,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#F97316", boxShadow: "0 0 8px #F97316" }} />
            Developer Infrastructure
          </div>

          <h1 
            style={{
              fontSize: "clamp(24px, 2.6vw, 34px)",
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: "-0.03em",
              color: "#F8FAFC",
              marginBottom: 12,
            }}
          >
            Ship software with autonomous coding agents.
          </h1>

          <p style={{ fontSize: 14, color: "#94A3B8", lineHeight: 1.55, maxWidth: 480, marginBottom: "clamp(16px, 2.5vh, 26px)" }}>
            Set up your organization in minutes. Connect your GitHub repositories, deploy isolated agent sandboxes, and enforce real cryptographic governance.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 480 }}>
            <CompactFeature 
              icon={Terminal} 
              title="Universal Agent Runtime Support" 
              desc="Full bidirectional compatibility with Claude Code, Cursor, Windsurf, Aider, and custom agent daemons via MCP."
            />
            <CompactFeature 
              icon={Layers} 
              title="Living Knowledge Graph" 
              desc="Agents query architectural dependencies before modifying code, preventing cross-file regressions."
            />
            <CompactFeature 
              icon={CheckCircle2} 
              title="Audit-Ready Compliance" 
              desc="Cryptographic traceability from human prompt to verified pull request and merge decision."
            />
          </div>
        </div>

        <div 
          style={{
            paddingTop: 14,
            borderTop: "1px solid rgba(255, 255, 255, 0.06)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: 11.5,
            color: "#64748B",
            fontFamily: "var(--font-mono, monospace)",
          }}
        >
          <span>SUTRA PROTOCOL // v1.4</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22C55E" }} />
            REGISTRATION OPEN
          </span>
        </div>
      </div>

      {/* Right Column: Console Form */}
      <div 
        style={{
          padding: "clamp(20px, 3vh, 40px) clamp(24px, 3vw, 48px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          zIndex: 2,
          overflow: "hidden",
        }}
      >
        <div style={{ width: "100%", maxWidth: 480 }}>
          {/* Double-Bezel Frame */}
          <div className="bezel-shell" style={{ width: "100%" }}>
            <div className="bezel-core" style={{ padding: "clamp(22px, 3.2vh, 32px) clamp(22px, 2.8vw, 34px)" }}>
              {step === "otp" ? (
                <>
                  <div style={{ textAlign: "center", marginBottom: 20 }}>
                    <div 
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: 12,
                        background: "rgba(249, 115, 22, 0.12)",
                        border: "1px solid rgba(249, 115, 22, 0.3)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "var(--accent, #F97316)",
                        margin: "0 auto 12px",
                      }}
                    >
                      <Mail size={20} />
                    </div>
                    <h2 style={{ fontSize: 22, fontWeight: 700, color: "#F8FAFC", marginBottom: 6 }}>
                      Confirm your email
                    </h2>
                    <p style={{ fontSize: 13, color: "#94A3B8", lineHeight: 1.45 }}>
                      We sent a 6-digit confirmation code to <strong style={{ color: "#F8FAFC" }}>{email}</strong>.
                    </p>
                  </div>

                  {error && (
                    <div 
                      style={{
                        color: "#F87171",
                        background: "rgba(239, 68, 68, 0.1)",
                        border: "1px solid rgba(239, 68, 68, 0.25)",
                        padding: "10px 14px",
                        borderRadius: 8,
                        fontSize: 13,
                        marginBottom: 16,
                      }}
                    >
                      {error}
                    </div>
                  )}

                  {successMsg && (
                    <div 
                      style={{
                        color: "#4ADE80",
                        background: "rgba(34, 197, 94, 0.1)",
                        border: "1px solid rgba(34, 197, 94, 0.25)",
                        padding: "10px 14px",
                        borderRadius: 8,
                        fontSize: 13,
                        marginBottom: 16,
                      }}
                    >
                      {successMsg}
                    </div>
                  )}

                  <form onSubmit={handleVerifyOtp}>
                    <div style={{ marginBottom: 20 }}>
                      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                        Verification Code
                      </label>
                      <input
                        className="input-recessed"
                        value={otp}
                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                        placeholder="••••••"
                        maxLength={6}
                        required
                        style={{
                          textAlign: "center",
                          fontSize: 20,
                          letterSpacing: "0.3em",
                          fontFamily: "var(--font-mono, monospace)",
                          fontWeight: 700,
                        }}
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={loading || otp.length !== 6}
                      className="btn-island"
                      style={{ 
                        width: "100%", 
                        height: 46,
                        justifyContent: "center", 
                        marginBottom: 10, 
                        fontSize: 14.5,
                        opacity: (loading || otp.length !== 6) ? 0.6 : 1 
                      }}
                    >
                      <span>{loading ? "Verifying..." : "Complete Registration"}</span>
                      <span className="icon-pill">
                        <ArrowRight size={13} />
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={cooldown > 0}
                      className="btn-island-ghost"
                      style={{ width: "100%", height: 42, justifyContent: "center", fontSize: 13.5 }}
                    >
                      <span>{cooldown > 0 ? `Resend Code (${cooldown}s)` : "Resend Code"}</span>
                    </button>
                  </form>
                </>
              ) : (
                <>
                  <div style={{ marginBottom: "clamp(16px, 2.2vh, 22px)" }}>
                    <div 
                      style={{
                        fontSize: 11,
                        fontFamily: "var(--font-mono, monospace)",
                        fontWeight: 600,
                        color: "var(--accent, #F97316)",
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        marginBottom: 6,
                      }}
                    >
                      YOUR JOURNEY BEGIN HERE WITH US
                    </div>
                    <h2 style={{ fontSize: "clamp(22px, 2.2vw, 25px)", fontWeight: 800, color: "#F8FAFC", letterSpacing: "-0.02em", marginBottom: 6 }}>
                      Create Your Account
                    </h2>
                    <p style={{ fontSize: 13, color: "#94A3B8" }}>
                      Get started with the SUTRA engineering control plane.
                    </p>
                  </div>

                  {error && (
                    <div 
                      style={{
                        color: "#F87171",
                        background: "rgba(239, 68, 68, 0.1)",
                        border: "1px solid rgba(239, 68, 68, 0.25)",
                        padding: "10px 14px",
                        borderRadius: 8,
                        fontSize: 13,
                        marginBottom: 16,
                        lineHeight: 1.4,
                      }}
                    >
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleSignup}>
                    <div style={{ marginBottom: 14 }}>
                      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                        Username
                      </label>
                      <input
                        className="input-recessed"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="example@mail.com"
                        required
                        autoComplete="username"
                      />
                    </div>

                    <div style={{ marginBottom: 14 }}>
                      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                        Work Email
                      </label>
                      <input
                        className="input-recessed"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="example@mail.com"
                        required
                        autoComplete="email"
                      />
                    </div>

                    <div style={{ marginBottom: 18 }}>
                      <label style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                        Password
                      </label>
                      <input
                        className="input-recessed"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Password"
                        required
                        autoComplete="new-password"
                      />
                    </div>

                    {/* Policy & Terms Agreement Notice */}
                    <div 
                      style={{ 
                        fontSize: 12, 
                        color: "#94A3B8", 
                        textAlign: "center", 
                        marginBottom: 14,
                        lineHeight: 1.5 
                      }}
                    >
                      By continuing, you agree to our{" "}
                      <Link href="/docs" style={{ color: "#F8FAFC", textDecoration: "underline" }}>
                        Policies
                      </Link>{" "}
                      and{" "}
                      <Link href="/docs" style={{ color: "#F8FAFC", textDecoration: "underline" }}>
                        Terms &amp; Conditions
                      </Link>.
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="btn-island"
                      style={{ 
                        width: "100%", 
                        height: 46, 
                        justifyContent: "center", 
                        marginBottom: 14, 
                        fontSize: 14.5,
                        fontWeight: 600,
                        opacity: loading ? 0.7 : 1 
                      }}
                    >
                      <span>{loading ? "Creating Organization..." : "Create Account & Continue"}</span>
                      <span className="icon-pill">
                        <ArrowRight size={13} />
                      </span>
                    </button>
                  </form>

                  <div style={{ textAlign: "center", fontSize: 13, color: "#94A3B8" }}>
                    Already have an account?{" "}
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
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
