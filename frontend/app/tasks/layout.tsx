import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Tasks — SUTRA",
  ...noIndexMetadata,
};

export default function TasksLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
