'use client';

import React, { useState, useRef } from 'react';

/**
 * 1. Spotlight Card (Aceternity UI)
 * Dynamic cursor-tracking radial spotlight card with smooth elevation and responsive glow.
 */
export function SpotlightCard({
  children,
  className = "",
  spotlightColor = "rgba(59, 130, 246, 0.15)",
  borderColor = "#212836",
  hoverBorderColor = "rgba(59, 130, 246, 0.4)",
  style = {},
  onClick
}: {
  children: React.ReactNode;
  className?: string;
  spotlightColor?: string;
  borderColor?: string;
  hoverBorderColor?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: -1000, y: -1000 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setMousePos({ x: -1000, y: -1000 });
      }}
      onClick={onClick}
      style={{
        position: "relative",
        background: "#10151C",
        border: `1px solid ${isHovered ? hoverBorderColor : borderColor}`,
        borderRadius: 16,
        padding: "24px",
        overflow: "hidden",
        transition: "border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease",
        transform: isHovered ? "translateY(-2px)" : "none",
        boxShadow: isHovered
          ? "0 12px 36px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(59, 130, 246, 0.1)"
          : "0 4px 16px rgba(0, 0, 0, 0.25)",
        ...style
      }}
      className={className}
    >
      {/* Radial Spotlight Overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(400px circle at ${mousePos.x}px ${mousePos.y}px, ${spotlightColor}, transparent 70%)`,
          opacity: isHovered ? 1 : 0,
          transition: "opacity 0.25s ease",
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}

/**
 * 2. Glowing Border Card (21st.dev / Aceternity)
 * Card with animated rotating gradient border accent.
 */
export function GlowingBorderCard({
  children,
  className = "",
  style = {},
  onClick
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        position: "relative",
        borderRadius: 16,
        padding: "1px",
        background: "linear-gradient(135deg, rgba(59, 130, 246, 0.4) 0%, rgba(99, 102, 241, 0.2) 50%, rgba(33, 40, 54, 0.8) 100%)",
        overflow: "hidden",
        ...style
      }}
      className={className}
    >
      <div
        style={{
          background: "#10151C",
          borderRadius: 15,
          padding: "24px",
          height: "100%",
        }}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * 3. Shimmer Border Button (21st.dev / Aceternity)
 * High-aesthetic primary button with animated sweeping light sheen.
 */
export function ShimmerButton({
  children,
  onClick,
  className = "",
  style = {},
  disabled = false,
  type = "button"
}: {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "10px 24px",
        borderRadius: 999,
        background: "linear-gradient(180deg, #3B82F6 0%, #2563EB 100%)",
        color: "#FFFFFF",
        fontSize: 14,
        fontWeight: 600,
        border: "none",
        cursor: disabled ? "not-allowed" : "pointer",
        overflow: "hidden",
        boxShadow: "0 0 20px rgba(59, 130, 246, 0.35)",
        transition: "all 0.18s ease",
        opacity: disabled ? 0.6 : 1,
        ...style
      }}
      className={className}
    >
      {/* Moving Shimmer Bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "-100%",
          width: "50%",
          height: "100%",
          background: "linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent)",
          transform: "skewX(-20deg)",
          animation: "shimmerMove 2.8s infinite",
        }}
      />
      <span style={{ position: "relative", zIndex: 1, display: "inline-flex", alignItems: "center", gap: 8 }}>
        {children}
      </span>
    </button>
  );
}

/**
 * 4. Glow Button (Aceternity UI)
 * Tactile button with radial halo and click micro-compression.
 */
export function GlowButton({
  children,
  onClick,
  tone = "blue",
  className = "",
  style = {},
  disabled = false,
  type = "button"
}: {
  children: React.ReactNode;
  onClick?: () => void;
  tone?: "blue" | "surface" | "indigo";
  className?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}) {
  const bg = tone === "blue" ? "#3B82F6" : tone === "indigo" ? "#6366F1" : "#171D26";
  const border = tone === "surface" ? "1px solid #212836" : "none";
  const textColor = "#FFFFFF";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "9px 20px",
        borderRadius: 10,
        background: bg,
        color: textColor,
        border: border,
        fontSize: 13,
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all 0.18s cubic-bezier(0.16, 1, 0.3, 1)",
        boxShadow: tone !== "surface" ? `0 4px 14px ${bg}40` : "none",
        opacity: disabled ? 0.6 : 1,
        ...style
      }}
      className={className}
    >
      {children}
    </button>
  );
}

/**
 * 5. Animated Icon Badge (21st.dev)
 * Glowing icon wrapper with soft aura and subtle hover lift.
 */
export function AnimatedIconBadge({
  icon: Icon,
  color = "#3B82F6",
  size = 20,
  boxSize = 40,
  style = {}
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color?: string;
  size?: number;
  boxSize?: number;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        width: boxSize,
        height: boxSize,
        borderRadius: 10,
        background: `${color}15`,
        border: `1px solid ${color}30`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: color,
        boxShadow: `0 0 16px ${color}20`,
        transition: "all 0.2s ease",
        ...style
      }}
    >
      <Icon size={size} />
    </div>
  );
}

/**
 * 6. Floating Status Badge (21st.dev)
 * Status badge with animated pulsing live radar dot.
 */
export function FloatingBadge({
  children,
  tone = "blue",
  pulsing = true
}: {
  children: React.ReactNode;
  tone?: "blue" | "green" | "amber" | "indigo";
  pulsing?: boolean;
}) {
  const colorMap = {
    blue: { bg: "rgba(59, 130, 246, 0.1)", border: "rgba(59, 130, 246, 0.28)", text: "#60A5FA", dot: "#3B82F6" },
    green: { bg: "rgba(34, 197, 94, 0.1)", border: "rgba(34, 197, 94, 0.28)", text: "#22C55E", dot: "#22C55E" },
    amber: { bg: "rgba(245, 158, 11, 0.1)", border: "rgba(245, 158, 11, 0.28)", text: "#F59E0B", dot: "#F59E0B" },
    indigo: { bg: "rgba(99, 102, 241, 0.1)", border: "rgba(99, 102, 241, 0.28)", text: "#818CF8", dot: "#6366F1" },
  };

  const current = colorMap[tone] || colorMap.blue;

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "4px 10px",
        borderRadius: 999,
        background: current.bg,
        border: `1px solid ${current.border}`,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        color: current.text,
      }}
    >
      {pulsing && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: current.dot,
            boxShadow: `0 0 8px ${current.dot}`,
            animation: "pulseGlow 2s infinite cubic-bezier(0.4, 0, 0.6, 1)",
          }}
        />
      )}
      {children}
    </div>
  );
}

/**
 * 7. Grid & Dot Mask Background (Aceternity UI)
 */
export function GridBackground({
  children,
  className = "",
  style = {}
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        overflow: "hidden",
        background: "#090C10",
        ...style
      }}
      className={className}
    >
      {/* Grid Pattern */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: "36px 36px",
          maskImage: "radial-gradient(ellipse 65% 50% at 50% 35%, black 40%, transparent 100%)",
          WebkitMaskImage: "radial-gradient(ellipse 65% 50% at 50% 35%, black 40%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
      {/* Radial Gradient Glow in Center */}
      <div
        style={{
          position: "absolute",
          top: "15%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "600px",
          height: "400px",
          background: "radial-gradient(circle, rgba(59, 130, 246, 0.12) 0%, rgba(99, 102, 241, 0.04) 40%, transparent 70%)",
          filter: "blur(60px)",
          pointerEvents: "none",
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}
