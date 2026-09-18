import type { Metadata } from "next";
import { Signup } from "@/components/auth";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Create Account — SUTRA",
  description: "Register for your SUTRA account.",
  ...noIndexMetadata,
};

export default function RegisterPage() {
  return <Signup />;
}
