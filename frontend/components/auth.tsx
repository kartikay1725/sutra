'use client';
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Btn } from "./shell";
import { authService } from "../lib/auth";
import { BookOpen, ArrowRight } from "lucide-react";

function Mark() {
  return <div className="mark" />;
}

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Unverified email verification state
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
        // If username was an email or user needs verification
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

  if (unverifiedEmail !== null) {
    return (
      <div className="auth">
        <div className="auth-card">
          <div className="auth-brand">
            <Mark />
            SUTRA
          </div>
          <div className="auth-title">Verify your email.</div>
          <div className="auth-sub">
            Please enter the 6-digit verification code sent to your email.
          </div>
          {otpError && (
            <div
              className="error-banner"
              style={{
                color: "#EF4444",
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {otpError}
            </div>
          )}
          {otpSuccess && (
            <div
              className="success-banner"
              style={{
                color: "#22C55E",
                background: "rgba(34, 197, 94, 0.1)",
                border: "1px solid rgba(34, 197, 94, 0.25)",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {otpSuccess}
            </div>
          )}
          <form onSubmit={handleVerifyOtp}>
            {!unverifiedEmail && (
              <div className="field">
                <label className="label">Registered Email Address</label>
                <input
                  className="input"
                  type="email"
                  value={unverifiedEmail || ""}
                  onChange={(e) => setUnverifiedEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                />
              </div>
            )}
            <div className="field">
              <label className="label">6-Digit Verification Code</label>
              <input
                className="input"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                maxLength={6}
                style={{ letterSpacing: "6px", fontSize: "16px", textAlign: "center" }}
                required
              />
            </div>
            <Btn primary style={{ width: "100%", marginBottom: 10 }} type="submit" disabled={otpLoading || otp.length !== 6}>
              {otpLoading ? "Verifying..." : "Verify & Sign In"}
            </Btn>
            <button
              type="button"
              className="btn"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={handleResendOtp}
              disabled={cooldown > 0 || !unverifiedEmail}
            >
              {cooldown > 0 ? `Resend Code (${cooldown}s)` : "Resend Code"}
            </button>
          </form>
          <div style={{ textAlign: "center", fontSize: 12, color: "#707A88", marginTop: 16 }}>
            <button
              type="button"
              onClick={() => {
                setUnverifiedEmail(null);
                setError("");
              }}
              style={{ background: "none", border: "none", color: "#60A5FA", cursor: "pointer", textDecoration: "underline" }}
            >
              Back to Sign In
            </button>
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
        <div className="auth-title">Welcome back.</div>
        <div className="auth-sub">Your engineering system is waiting.</div>
        {error && (
          <div
            className="error-banner"
            style={{
              color: "#EF4444",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              padding: "8px 12px",
              borderRadius: 6,
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}
        <form onSubmit={handleLogin}>
          <div className="field">
            <label className="label">Username or Email</label>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="alex or alex@company.com"
              required
            />
          </div>
          <div className="field">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label className="label" style={{ marginBottom: 0 }}>Password</label>
              <Link href="/forgot-password" className="auth-link" style={{ fontSize: 11 }}>
                Forgot password?
              </Link>
            </div>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{ marginTop: 4 }}
            />
          </div>
          <Btn primary style={{ width: "100%" }} type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Btn>
        </form>

        {error.toLowerCase().includes("verify your email") && (
          <div style={{ textAlign: "center", marginTop: 12 }}>
            <button
              type="button"
              onClick={() => setUnverifiedEmail(username.includes("@") ? username : "")}
              className="auth-link"
              style={{ background: "none", border: "none", fontSize: 12, cursor: "pointer" }}
            >
              Enter verification code / Resend code
            </button>
          </div>
        )}

        <div className="divider">Or continue with:</div>
        <button
          className="btn"
          style={{
            width: "100%",
            justifyContent: "center",
            opacity: 0.6,
            cursor: "not-allowed",
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "#171D26",
            border: "1px solid #212836",
          }}
          type="button"
          disabled
          aria-disabled="true"
        >
          Sign in with Single Sign-On (SSO)
          <span
            style={{
              fontSize: 10,
              background: "rgba(255, 255, 255, 0.08)",
              padding: "2px 6px",
              borderRadius: 4,
              color: "#A8B1BD",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Coming Soon
          </span>
        </button>

        <div style={{ textAlign: "center", fontSize: 12, color: "#707A88", marginTop: 16 }}>
          Don't have an account?{" "}
          <Link href="/signup" className="auth-link">
            Sign up
          </Link>
        </div>

        <div style={{ textAlign: "center", marginTop: 16, borderTop: "1px solid #212836", paddingTop: 14 }}>
          <Link
            href="/docs#human-quickstart"
            style={{
              fontSize: 12,
              color: "#707A88",
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <BookOpen size={13} />
            Need help? Read Quickstart Guide
          </Link>
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
    <div className="auth">
      <div className="auth-card">
        <div className="auth-brand">
          <Mark />
          SUTRA
        </div>
        <div className="auth-title">
          {step === "form" ? "Build with intent." : "Verify your email."}
        </div>
        <div className="auth-sub">
          {step === "form"
            ? "The engineering OS for autonomous agents."
            : `We sent a 6-digit verification code to ${email}.`}
        </div>
        
        {error && (
          <div
            className="error-banner"
            style={{
              color: "#EF4444",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              padding: "8px 12px",
              borderRadius: 6,
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}
        {successMsg && step === "otp" && (
          <div
            className="success-banner"
            style={{
              color: "#22C55E",
              background: "rgba(34, 197, 94, 0.1)",
              border: "1px solid rgba(34, 197, 94, 0.25)",
              padding: "8px 12px",
              borderRadius: 6,
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {successMsg}
          </div>
        )}

        {step === "form" ? (
          <form onSubmit={handleSignup}>
            <div className="field">
              <label className="label">Username</label>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="alex"
                required
              />
            </div>
            <div className="field">
              <label className="label">Email Address</label>
              <input
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                type="email"
                required
              />
            </div>
            <div className="field">
              <label className="label">Password</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                minLength={8}
                required
              />
            </div>
            <Btn primary style={{ width: "100%" }} type="submit" disabled={loading}>
              {loading ? "Creating account..." : "Join Private Beta"}
            </Btn>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp}>
            <div className="field">
              <label className="label">6-Digit Verification Code</label>
              <input
                className="input"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                maxLength={6}
                style={{ letterSpacing: "6px", fontSize: "16px", textAlign: "center" }}
                required
              />
            </div>
            <Btn primary style={{ width: "100%", marginBottom: 10 }} type="submit" disabled={loading || otp.length !== 6}>
              {loading ? "Verifying..." : "Verify & Continue"}
            </Btn>
            <button
              type="button"
              className="btn"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={handleResendOtp}
              disabled={cooldown > 0}
            >
              {cooldown > 0 ? `Resend Code (${cooldown}s)` : "Resend Code"}
            </button>
          </form>
        )}

        <div style={{ textAlign: "center", fontSize: 12, color: "#707A88", marginTop: 16 }}>
          {step === "form" ? (
            <>
              Already have an account?{" "}
              <Link href="/login" className="auth-link">
                Sign in
              </Link>
            </>
          ) : (
            <button
              type="button"
              onClick={() => {
                setStep("form");
                setError("");
              }}
              style={{ background: "none", border: "none", color: "#60A5FA", cursor: "pointer", textDecoration: "underline" }}
            >
              Change registration details
            </button>
          )}
        </div>

        <div style={{ textAlign: "center", marginTop: 16, borderTop: "1px solid #212836", paddingTop: 14 }}>
          <Link
            href="/docs#human-quickstart"
            style={{
              fontSize: 12,
              color: "#707A88",
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <BookOpen size={13} />
            Need help? Read Quickstart Guide
          </Link>
        </div>
      </div>
    </div>
  );
}
