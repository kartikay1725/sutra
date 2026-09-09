"use client";

import React, { useEffect, useState } from "react";

const SUTRA_DEV_QUOTES = [
  "“Autonomous agents are reading your git commit history and judging your variable names...”",
  "“Aligning sovereign governance policies with reality...”",
  "“Resolving dependency tree conflicts without summoning a black hole...”",
  "“Teaching agents why you shouldn't git push --force on main on a Friday...”",
  "“Compiling knowledge graph nodes into actionable engineering intent...”",
  "“Verifying that the tests actually test what they claim to test...”",
  "“Asking the CI pipeline nicely to pass on the first try...”",
  "“Re-hydrating developer synapses with fresh telemetry...”",
  "“Calibrating the governance engine to prevent rogue agents...”",
  "“Untangling human intent into deterministic software state...”",
  "“Benchmarking latency between thought and governed pull request...”",
  "“Ensuring no TODO comments from 2021 made it into the release...”"
];

export function SutraLoading({
  message,
  quote,
  fullscreen = false,
}: {
  message?: string;
  quote?: boolean;
  fullscreen?: boolean;
}) {
  const [quoteIndex, setQuoteIndex] = useState(0);
  const [fade, setFade] = useState(true);

  useEffect(() => {
    // Pick initial random quote
    setQuoteIndex(Math.floor(Math.random() * SUTRA_DEV_QUOTES.length));

    if (quote !== false) {
      const interval = setInterval(() => {
        setFade(false);
        setTimeout(() => {
          setQuoteIndex((prev) => (prev + 1) % SUTRA_DEV_QUOTES.length);
          setFade(true);
        }, 220);
      }, 3400);

      return () => clearInterval(interval);
    }
  }, [quote]);

  return (
    <div
      className={fullscreen ? "sutra-loading-fullscreen" : "sutra-loading-container"}
      role="status"
      aria-label="Loading SUTRA"
    >
      {/* Kinetic Harmonic S-Spinner */}
      <div className="sutra-spinner-wrapper">
        <svg
          className="sutra-s-spinner-svg"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="sutraGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#6366f1" />
            </linearGradient>
            <linearGradient id="sutraGrad2" x1="100%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="#8b5cf6" />
              <stop offset="100%" stopColor="#38bdf8" />
            </linearGradient>
            <filter id="sutraGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Faint orbit trace */}
          <circle
            cx="32"
            cy="32"
            r="24"
            stroke="rgba(59, 130, 246, 0.12)"
            strokeWidth="1.5"
            strokeDasharray="3 5"
          />

          {/* Top orbital arc - counter-rotating harmonic */}
          <path
            className="sutra-arc-top"
            d="M 32,32 C 32,20 44,14 44,22 C 44,30 32,32 32,32"
            stroke="url(#sutraGrad1)"
            strokeWidth="3.2"
            strokeLinecap="round"
            filter="url(#sutraGlow)"
          />

          {/* Bottom orbital arc - counter-rotating harmonic */}
          <path
            className="sutra-arc-bottom"
            d="M 32,32 C 32,44 20,50 20,42 C 20,34 32,32 32,32"
            stroke="url(#sutraGrad2)"
            strokeWidth="3.2"
            strokeLinecap="round"
            filter="url(#sutraGlow)"
          />

          {/* Central sovereign quantum vortex node */}
          <circle
            className="sutra-spinner-center-node"
            cx="32"
            cy="32"
            r="2.5"
            fill="#60a5fa"
          />
        </svg>
      </div>

      {/* Primary Status Text */}
      <div className="sutra-loading-text">
        <span className="sutra-loading-brand">SUTRA</span>
        <span className="sutra-loading-dots">
          <span />
          <span />
          <span />
        </span>
      </div>

      {message && <div className="sutra-loading-sub">{message}</div>}

      {/* Engaging & Humorous Engineering Quotes */}
      {quote !== false && (
        <div
          className={`sutra-loading-quote ${fade ? "sutra-fade-in" : "sutra-fade-out"}`}
        >
          {SUTRA_DEV_QUOTES[quoteIndex]}
        </div>
      )}
    </div>
  );
}
