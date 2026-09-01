import Link from "next/link";
import React from "react";

export function Page({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
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
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean; violet?: boolean }) {
  return (
    <button
      className={"btn " + (primary ? "primary " : "") + (violet ? "violet" : "")}
      {...props}
    >
      {children}
    </button>
  );
}

