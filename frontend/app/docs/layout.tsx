import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Documentation | SUTRA — AI-Native Engineering Control Plane",
  description:
    "Official technical documentation for SUTRA by AchintAI: bounded AI agent authority, cryptographic commit provenance, Model Context Protocol (MCP), and governed pull requests.",
  category: "AI-Native Engineering Control Plane",
  alternates: {
    canonical: "/docs",
  },
  openGraph: {
    title: "Documentation | SUTRA — AI-Native Engineering Control Plane",
    description:
      "Official technical documentation for SUTRA by AchintAI: bounded AI agent authority, cryptographic commit provenance, Model Context Protocol (MCP), and governed pull requests.",
    url: "/docs",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo-s.png",
        width: 1200,
        height: 630,
        alt: "SUTRA Documentation — AI-Native Engineering Control Plane by AchintAI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Documentation | SUTRA — AI-Native Engineering Control Plane",
    description:
      "Official technical documentation for SUTRA by AchintAI: bounded AI agent authority, cryptographic commit provenance, Model Context Protocol (MCP), and governed pull requests.",
    images: ["/logo-s.png"],
  },
};

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
