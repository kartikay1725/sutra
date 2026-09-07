import type { Metadata } from "next";
import { AppShell } from "@/components/shell";
import { Dashboard } from "@/components/dashboard";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Dashboard — SUTRA",
  ...noIndexMetadata,
};

export default function Page() {
  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}
