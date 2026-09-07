import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Audit Log — SUTRA",
  ...noIndexMetadata,
};

export default function AuditLogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
