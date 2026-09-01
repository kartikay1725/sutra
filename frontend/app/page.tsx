"use client";

import { useState, useEffect } from "react";
import { AppShell } from "@/components/shell";
import { Dashboard } from "@/components/dashboard";
import { LandingPage } from "@/components/landing_page";
import { authService } from "@/lib/auth";

export default function Page() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    setIsAuthenticated(authService.isAuthenticated());
  }, []);

  // During SSR or before client hydration check, render the public LandingPage for fast loading and full SEO indexability
  if (isAuthenticated === null) {
    return <LandingPage />;
  }

  if (isAuthenticated) {
    return (
      <AppShell>
        <Dashboard />
      </AppShell>
    );
  }

  return <LandingPage />;
}
