import type { Metadata } from "next";
import { ResetPassword } from "@/components/reset_password";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Reset Password — SUTRA",
  ...noIndexMetadata,
};

export default function ResetPasswordPage() {
  return <ResetPassword />;
}
