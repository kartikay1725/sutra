"use client";

import React from "react";
import { Card } from "@/components/shell";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({
  width = "100%",
  height = 16,
  borderRadius = 6,
  className = "",
  style = {},
  ...props
}: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{
        width,
        height,
        borderRadius,
        display: "inline-block",
        ...style,
      }}
      {...props}
    />
  );
}

/**
 * File Tree Skeleton for the repository code page left sidebar
 */
export function SkeletonFileTree({ count = 8 }: { count?: number }) {
  const widths = ["65%", "45%", "80%", "55%", "70%", "38%", "60%", "75%", "50%", "68%"];
  const isDir = [true, true, false, false, true, false, false, false, false, false];
  const indents = [0, 0, 16, 16, 0, 16, 16, 0, 0, 0];

  return (
    <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: count }).map((_, i) => {
        const dir = isDir[i % isDir.length];
        const indent = indents[i % indents.length];
        const width = widths[i % widths.length];

        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 8px",
              paddingLeft: 8 + indent,
              borderRadius: 6,
            }}
          >
            <Skeleton
              width={14}
              height={14}
              borderRadius={3}
              style={{ flexShrink: 0, opacity: dir ? 0.7 : 0.5 }}
            />
            <Skeleton
              width={width}
              height={13}
              borderRadius={4}
              style={{ opacity: 0.65 }}
            />
          </div>
        );
      })}
    </div>
  );
}

/**
 * Code File Viewer Skeleton with line numbers gutter and syntax-like lines
 */
export function SkeletonCodeViewer({ lines = 16 }: { lines?: number }) {
  const linePatterns = [
    { indent: 0, width: "35%" },
    { indent: 0, width: "50%" },
    { indent: 0, width: "0%" },
    { indent: 0, width: "45%" },
    { indent: 16, width: "70%" },
    { indent: 16, width: "55%" },
    { indent: 32, width: "65%" },
    { indent: 32, width: "40%" },
    { indent: 16, width: "30%" },
    { indent: 0, width: "10%" },
    { indent: 0, width: "0%" },
    { indent: 0, width: "60%" },
    { indent: 16, width: "80%" },
    { indent: 16, width: "50%" },
    { indent: 32, width: "60%" },
    { indent: 0, width: "15%" },
  ];

  return (
    <div
      style={{
        padding: "20px 24px",
        fontFamily: "var(--font-mono, monospace)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {Array.from({ length: lines }).map((_, i) => {
        const pattern = linePatterns[i % linePatterns.length];
        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              height: 20,
            }}
          >
            <span
              style={{
                width: 28,
                textAlign: "right",
                fontSize: 12,
                color: "var(--muted)",
                opacity: 0.3,
                userSelect: "none",
                flexShrink: 0,
              }}
            >
              {i + 1}
            </span>
            {pattern.width !== "0%" ? (
              <Skeleton
                width={pattern.width}
                height={13}
                borderRadius={4}
                style={{ marginLeft: pattern.indent, opacity: 0.6 }}
              />
            ) : (
              <div style={{ height: 13 }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Commit List Skeleton
 */
export function SkeletonCommitList({ count = 5 }: { count?: number }) {
  return (
    <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          style={{
            padding: "12px 14px",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--bg-subtle)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Skeleton width="60%" height={14} borderRadius={4} />
            <Skeleton width={68} height={20} borderRadius={4} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Skeleton width={18} height={18} borderRadius="50%" />
            <Skeleton width={120} height={12} borderRadius={3} />
            <Skeleton width={80} height={12} borderRadius={3} />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Pull Request Card List Skeleton
 */
export function SkeletonPRList({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1 }}>
              <Skeleton width={20} height={20} borderRadius="50%" style={{ flexShrink: 0, opacity: 0.6 }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
                <Skeleton width={`${45 + (i % 3) * 15}%`} height={16} borderRadius={4} />
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Skeleton width={90} height={18} borderRadius={4} />
                  <Skeleton width={80} height={12} borderRadius={3} />
                  <Skeleton width={110} height={12} borderRadius={3} />
                </div>
              </div>
            </div>
            <Skeleton width={72} height={22} borderRadius={12} style={{ flexShrink: 0 }} />
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Issues List Skeleton
 */
export function SkeletonIssueList({ count = 5 }: { count?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} style={{ padding: "14px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
              <Skeleton width={16} height={16} borderRadius="50%" style={{ flexShrink: 0, opacity: 0.6 }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                <Skeleton width={`${50 + (i % 4) * 10}%`} height={15} borderRadius={4} />
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Skeleton width={50} height={12} borderRadius={3} />
                  <Skeleton width={80} height={12} borderRadius={3} />
                  <Skeleton width={60} height={16} borderRadius={4} />
                </div>
              </div>
            </div>
            <Skeleton width={32} height={14} borderRadius={4} style={{ flexShrink: 0 }} />
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Changes List Skeleton
 */
export function SkeletonChangeList({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
              <Skeleton width={18} height={18} borderRadius={4} style={{ flexShrink: 0, opacity: 0.6 }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                <Skeleton width={`${40 + (i % 3) * 15}%`} height={15} borderRadius={4} />
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Skeleton width={70} height={12} borderRadius={3} />
                  <Skeleton width={100} height={12} borderRadius={3} />
                </div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Skeleton width={60} height={20} borderRadius={4} />
              <Skeleton width={70} height={20} borderRadius={4} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Agents List Skeleton
 */
export function SkeletonAgentList({ count = 3 }: { count?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} style={{ padding: "18px 22px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1 }}>
              <Skeleton width={36} height={36} borderRadius="50%" style={{ flexShrink: 0 }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                <Skeleton width={140} height={16} borderRadius={4} />
                <Skeleton width={220} height={12} borderRadius={3} />
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Skeleton width={90} height={20} borderRadius={4} />
              <Skeleton width={70} height={20} borderRadius={10} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * CI Runs Skeleton
 */
export function SkeletonCIRuns({ count = 4 }: { count?: number }) {
  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            style={{
              padding: "16px 20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: i < count - 1 ? "1px solid var(--line)" : "none",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1 }}>
              <Skeleton width={18} height={18} borderRadius="50%" style={{ flexShrink: 0 }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                <Skeleton width={`${35 + (i % 3) * 15}%`} height={15} borderRadius={4} />
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Skeleton width={70} height={12} borderRadius={3} />
                  <Skeleton width={90} height={12} borderRadius={3} />
                </div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Skeleton width={60} height={12} borderRadius={3} />
              <Skeleton width={70} height={22} borderRadius={11} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/**
 * Repository Overview Skeleton
 */
export function SkeletonRepoOverview() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header Info */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 8 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>
          <Skeleton width={180} height={28} borderRadius={6} />
          <Skeleton width={320} height={14} borderRadius={4} />
        </div>
        <Skeleton width={80} height={24} borderRadius={12} />
      </div>

      {/* Metric Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} style={{ padding: "18px 20px" }}>
            <Skeleton width={80} height={12} borderRadius={3} style={{ marginBottom: 10 }} />
            <Skeleton width={110} height={26} borderRadius={5} />
          </Card>
        ))}
      </div>

      {/* Recent Activity / Commits Feed */}
      <Card style={{ padding: "20px 24px" }}>
        <Skeleton width={150} height={16} borderRadius={4} style={{ marginBottom: 16 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 10, borderBottom: i < 3 ? "1px solid var(--line)" : "none" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                <Skeleton width={16} height={16} borderRadius="50%" style={{ flexShrink: 0 }} />
                <Skeleton width={`${40 + (i % 3) * 15}%`} height={14} borderRadius={4} />
              </div>
              <Skeleton width={90} height={12} borderRadius={3} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

/**
 * Repository Settings Skeleton
 */
export function SkeletonRepoSettings() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 8 }}>
        <Skeleton width={200} height={24} borderRadius={6} />
        <Skeleton width={340} height={14} borderRadius={4} />
      </div>

      <Card style={{ padding: "24px 28px" }}>
        <Skeleton width={160} height={18} borderRadius={4} style={{ marginBottom: 20 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div>
            <Skeleton width={120} height={12} borderRadius={3} style={{ marginBottom: 8 }} />
            <Skeleton width="100%" height={38} borderRadius={6} />
          </div>
          <div>
            <Skeleton width={100} height={12} borderRadius={3} style={{ marginBottom: 8 }} />
            <Skeleton width="100%" height={38} borderRadius={6} />
          </div>
          <div>
            <Skeleton width={140} height={12} borderRadius={3} style={{ marginBottom: 8 }} />
            <Skeleton width="100%" height={76} borderRadius={6} />
          </div>
          <Skeleton width={110} height={36} borderRadius={6} style={{ alignSelf: "flex-start", marginTop: 6 }} />
        </div>
      </Card>
    </div>
  );
}
