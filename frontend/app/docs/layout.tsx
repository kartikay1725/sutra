import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SUTRA Documentation — AI-Native Engineering",
  description:
    "Official technical documentation for SUTRA by Sudarshan Harness: agent registration, session-bound Git auth, task lifecycles, and governed pull requests.",
  alternates: {
    canonical: "/docs",
  },
  openGraph: {
    title: "SUTRA Documentation — AI-Native Engineering",
    description:
      "Official technical documentation for SUTRA by Sudarshan Harness: agent registration, session-bound Git auth, task lifecycles, and governed pull requests.",
    url: "/docs",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "SUTRA Documentation — AI-Native Engineering",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "SUTRA Documentation — AI-Native Engineering",
    description:
      "Official technical documentation for SUTRA by Sudarshan Harness: agent registration, session-bound Git auth, task lifecycles, and governed pull requests.",
    images: ["/og-image.png"],
  },
};

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
