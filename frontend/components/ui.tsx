import Link from "next/link";
import React from "react";

export function Page({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="content">
      <div className="page-hero">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="topactions">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

export function Card({
  children,
  className = "",
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return <div className={"card " + className} style={style}>{children}</div>;
}

export function Badge({
  children,
  tone = "",
  style,
}: {
  children: React.ReactNode;
  tone?: string;
  style?: React.CSSProperties;
}) {
  return (
    <span className={"badge " + tone} style={style}>
      <i className="dot" />
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <Card>
      <div className="statlabel">{label}</div>
      <div className="statvalue">{value}</div>
      <div className="sub">{sub}</div>
    </Card>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="btn" {...props} />;
}

export function Btn({
  children,
  primary = false,
  violet = false,
  sm = false,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean; violet?: boolean; sm?: boolean }) {
  return (
    <button
      className={`btn ${primary ? "primary " : ""}${violet ? "violet " : ""}${sm ? "sm " : ""}${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <div className="empty-state-title">{title}</div>
      {description && <div className="empty-state-desc">{description}</div>}
      {action && <div>{action}</div>}
    </div>
  );
}

export function Table({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="table-container">
      <table className={"table " + className}>{children}</table>
    </div>
  );
}

export { SutraLoading } from "./sutra-loading";
