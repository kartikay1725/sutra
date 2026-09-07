import type { Metadata } from "next";
import { ForgotPassword } from "@/components/forgot_password";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Forgot Password — SUTRA",
  ...noIndexMetadata,
};

export default function ForgotPasswordPage() {
  return <ForgotPassword />;
}
