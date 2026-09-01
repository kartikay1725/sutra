import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://sutra.dev"),
  title: {
    default: "SUTRA — AI agents that can actually ship software",
    template: "%s | SUTRA",
  },
  description:
    "SUTRA gives AI agents controlled identity, repository-scoped access, real Git workflows, verification, and human review.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "SUTRA — AI agents that can actually ship software",
    description:
      "SUTRA gives AI agents controlled identity, repository-scoped access, real Git workflows, verification, and human review.",
    url: "/",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo-s.png",
        width: 512,
        height: 512,
        alt: "SUTRA — AI Agent Engineering Infrastructure",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "SUTRA — AI agents that can actually ship software",
    description:
      "SUTRA gives AI agents controlled identity, repository-scoped access, real Git workflows, verification, and human review.",
    images: ["/logo-s.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}