import type { Metadata } from "next";
import { AboutPage } from "@/components/about_page";

export const metadata: Metadata = {
  title: "About SUTRA — AI Agent Engineering Infrastructure",
  description:
    "SUTRA is building the control layer for AI software agents to perform real engineering work with bounded authority and human oversight.",
  alternates: {
    canonical: "/about",
  },
  openGraph: {
    title: "About SUTRA — AI Agent Engineering Infrastructure",
    description:
      "SUTRA is building the control layer for AI software agents to perform real engineering work with bounded authority and human oversight.",
    url: "/about",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "About SUTRA — AI Agent Engineering Infrastructure",
    description:
      "SUTRA is building the control layer for AI software agents to perform real engineering work with bounded authority and human oversight.",
  },
};

export default function Page() {
  return <AboutPage />;
}
