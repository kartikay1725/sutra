import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Enterprise Governance & Policy Controls — SUTRA",
  description:
    "Enterprise controls for autonomous AI software engineering: SAML SSO, immutable audit trails, branch protection, and branch governance policies.",
  alternates: {
    canonical: "/enterprise",
  },
  openGraph: {
    title: "Enterprise Governance & Policy Controls — SUTRA",
    description:
      "Enterprise controls for autonomous AI software engineering: SAML SSO, immutable audit trails, branch protection, and branch governance policies.",
    url: "/enterprise",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Enterprise Governance — SUTRA",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Enterprise Governance & Policy Controls — SUTRA",
    description:
      "Enterprise controls for autonomous AI software engineering: SAML SSO, immutable audit trails, branch protection, and branch governance policies.",
    images: ["/og-image.png"],
  },
};

export default function EnterpriseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
