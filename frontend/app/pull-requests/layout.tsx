import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Pull Requests — SUTRA",
  ...noIndexMetadata,
};

export default function PullRequestsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
