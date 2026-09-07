import type { Metadata } from "next";
import { Login } from "@/components/auth";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Sign In — SUTRA",
  description: "Sign in to the SUTRA engineering control plane.",
  ...noIndexMetadata,
};

export default function Page() {
  return <Login />;
}