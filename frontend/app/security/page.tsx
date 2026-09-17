import type { Metadata } from "next";
import { ShieldCheck } from "lucide-react";
import { Page, Card } from "@/components/ui";
import { AppShell } from "@/components/shell";

export const metadata: Metadata = {
  title: "Security Architecture & Cryptographic Trust — SUTRA",
  description:
    "SUTRA cryptographic event integrity, secret segregation, short-lived session boundaries, and capability-based authorization.",
  alternates: {
    canonical: "/security",
  },
  openGraph: {
    title: "Security Architecture & Cryptographic Trust — SUTRA",
    description:
      "SUTRA cryptographic event integrity, secret segregation, short-lived session boundaries, and capability-based authorization.",
    url: "/security",
    siteName: "SUTRA",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo-s.png",
        width: 1200,
        height: 630,
        alt: "Security Architecture — SUTRA",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Security Architecture & Cryptographic Trust — SUTRA",
    description:
      "SUTRA cryptographic event integrity, secret segregation, short-lived session boundaries, and capability-based authorization.",
    images: ["/logo-s.png"],
  },
};

export default function Security() {
  return (
    <AppShell isPublic>
      <Page
        eyebrow="Trust & Security"
        title="Security Architecture"
        description="Cryptographic event verification, capability isolation, and automated policy signals."
      >
        <div className="grid grid4">
          <Card>
            <div className="statlabel">Security state</div>
            <div className="statvalue green">Clean</div>
            <div className="sub">Cryptographic verification active</div>
          </Card>
          <Card>
            <div className="statlabel">Critical</div>
            <div className="statvalue green">0</div>
            <div className="sub">open policy findings</div>
          </Card>
          <Card>
            <div className="statlabel">High</div>
            <div className="statvalue green">0</div>
            <div className="sub">open policy findings</div>
          </Card>
          <Card>
            <div className="statlabel">Policy</div>
            <div className="statvalue cyan">ENFORCED</div>
            <div className="sub">branch protection rules</div>
          </Card>
        </div>
        <Card className="section">
          <div className="statusline green">
            <ShieldCheck size={16} /> No blocking security findings across active changes.
          </div>
        </Card>
      </Page>
    </AppShell>
  );
}