import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Activity — SUTRA",
  ...noIndexMetadata,
};

export default function ActivityLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
