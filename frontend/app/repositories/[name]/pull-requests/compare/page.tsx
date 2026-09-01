"use client";
// This page is superseded by /pull-requests/new — redirect automatically
import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell";

export default function CompareRedirect({ params }: { params: Promise<{ name: string }> }) {
  const { name } = use(params);
  const router = useRouter();
  useEffect(() => {
    router.replace(`/repositories/${name}/pull-requests/new`);
  }, [name]);
  return <AppShell><div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>Redirecting…</div></AppShell>;
}
