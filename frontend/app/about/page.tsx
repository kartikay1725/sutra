import type { Metadata } from "next";
import { AboutPage } from "@/components/about_page";

export const metadata: Metadata = {
  title: "About SUTRA — AI-Native Engineering Control Plane",
  description:
    "Learn about SUTRA by AchintAI: an AI-native engineering control plane providing bounded authority, real Git workflows, and human review for autonomous engineering.",
  alternates: {
    canonical: "/about",
  },
  openGraph: {
    title: "About SUTRA — AI-Native Engineering Control Plane",
    description:
      "Learn about SUTRA by AchintAI: an AI-native engineering control plane providing bounded authority, real Git workflows, and human review for autonomous engineering.",
    url: "/about",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo-s.png",
        width: 1200,
        height: 630,
        alt: "About SUTRA — AI-Native Engineering Control Plane",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "About SUTRA — AI-Native Engineering Control Plane",
    description:
      "Learn about SUTRA by AchintAI: an AI-native engineering control plane providing bounded authority, real Git workflows, and human review for autonomous engineering.",
    images: ["/logo-s.png"],
  },
};

export default function Page() {
  return <AboutPage />;
}
