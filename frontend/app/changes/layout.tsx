import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Changes — SUTRA",
  ...noIndexMetadata,
};

export default function ChangesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
