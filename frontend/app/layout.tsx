import type { Metadata, Viewport } from "next";
import "./globals.css";
import { GoogleAnalytics } from "@/components/analytics";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: "#090C10",
};

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://sutra.sudarshanai.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "SUTRA — AI-Native Engineering Control Plane",
    template: "%s | SUTRA",
  },
  description:
    "SUTRA is an AI-native engineering control plane by Sudarshan Harness for governed autonomous software engineering, repository access, and human review.",
  applicationName: "SUTRA",
  authors: [{ name: "Sudarshan Harness", url: "https://sudarshanai.com" }],
  creator: "Sudarshan Harness",
  publisher: "Sudarshan Harness",
  category: "technology",
  keywords: [
    "SUTRA",
    "AI-native engineering control plane",
    "governed autonomous software engineering",
    "AI agents",
    "software engineering governance",
    "Sudarshan Harness",
    "Git automation",
    "human review",
    "code verification",
  ],
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.png", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: "/icon.png",
  },
  openGraph: {
    title: "SUTRA — AI-Native Engineering Control Plane",
    description:
      "SUTRA is an AI-native engineering control plane by Sudarshan Harness for governed autonomous software engineering, repository access, and human review.",
    url: "/",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logos-s.png",
        width: 1200,
        height: 630,
        alt: "SUTRA — AI-Native Engineering Control Plane by Sudarshan Harness",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "SUTRA — AI-Native Engineering Control Plane",
    description:
      "SUTRA is an AI-native engineering control plane by Sudarshan Harness for governed autonomous software engineering, repository access, and human review.",
    images: ["/logo-s.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  verification: process.env.GOOGLE_SITE_VERIFICATION
    ? {
      google: process.env.GOOGLE_SITE_VERIFICATION,
    }
    : undefined,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <GoogleAnalytics />
        {children}
      </body>
    </html>
  );
}