"use client";

import React, { useEffect, useState } from "react";

const SUTRA_DEV_QUOTES = [
  "\u201cAutonomous agents are reading your git commit history and judging your variable names...\u201d",
  "\u201cAligning sovereign governance policies with reality...\u201d",
  "\u201cResolving dependency tree conflicts without summoning a black hole...\u201d",
  "\u201cTeaching agents why you shouldn\u2019t git push --force on main on a Friday...\u201d",
  "\u201cCompiling knowledge graph nodes into actionable engineering intent...\u201d",
  "\u201cVerifying that the tests actually test what they claim to test...\u201d",
  "\u201cAsking the CI pipeline nicely to pass on the first try...\u201d",
  "\u201cRe-hydrating developer synapses with fresh telemetry...\u201d",
  "\u201cCalibrating the governance engine to prevent rogue agents...\u201d",
  "\u201cUntangling human intent into deterministic software state...\u201d",
  "\u201cBenchmarking latency between thought and governed pull request...\u201d",
  "\u201cEnsuring no TODO comments from 2021 made it into the release...\u201d",
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
      {/* S-Shape Kinetic Spinner */}
      <div className="sutra-spinner-wrapper">
        <svg
          className="sutra-s-spinner-svg"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="sutraGradS" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="50%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#3b82f6" />
            </linearGradient>
            <filter id="sutraGlowS" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/*
            True S-curve:
            Starts top-right area, curves left-down through center,
            then curves right-down to bottom-left.
            This is a single cubic-bezier path that traces a clean S letterform.
          */}
          <path
            className="sutra-s-path"
            d="
              M 44,16
              C 44,10 20,10 20,22
              C 20,32 44,32 44,42
              C 44,54 20,54 20,48
            "
            stroke="url(#sutraGradS)"
            strokeWidth="4.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#sutraGlowS)"
          />

          {/* Glowing end-cap dot that traces the S */}
          <circle
            className="sutra-s-dot"
            r="3"
            fill="#60a5fa"
            filter="url(#sutraGlowS)"
          >
            <animateMotion
              dur="2s"
              repeatCount="indefinite"
              keyTimes="0;0.5;1"
              keySplines="0.42 0 0.58 1; 0.42 0 0.58 1"
              calcMode="spline"
            >
              <mpath href="#sutra-s-motion-path" />
            </animateMotion>
          </circle>

          {/* Hidden path for animateMotion reference */}
          <path
            id="sutra-s-motion-path"
            d="
              M 44,16
              C 44,10 20,10 20,22
              C 20,32 44,32 44,42
              C 44,54 20,54 20,48
            "
            fill="none"
            stroke="none"
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
