import type { Metadata } from "next";
import { Signup } from "@/components/auth";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Join Private Beta — SUTRA",
  description: "Request access or register for the SUTRA private beta.",
  ...noIndexMetadata,
};

export default function RegisterPage() {
  return <Signup />;
}
