import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://sutra.sudarshanai.com";

  return {
    rules: {
      userAgent: "*",
      allow: [
        "/",
        "/about",
        "/docs",
        "/enterprise",
        "/security",
        "/robots.txt",
        "/sitemap.xml",
        "/favicon.ico",
        "/icon.png",
        "/logo-s.png",
        "/logo.svg",
      ],
      disallow: [
        "/v1/",
        "/api/",
        "/repositories/",
        "/tasks/",
        "/changes/",
        "/pull-requests/",
        "/ci/",
        "/agents/",
        "/repo-agents/",
        "/audit-log/",
        "/activity/",
        "/assistant/",
        "/knowledge-graph/",
        "/insights/",
        "/marketplace/",
        "/organizations/",
        "/my-work/",
        "/profile/",
        "/notifications/",
        "/environments/",
        "/deployments/",
        "/login",
        "/register",
        "/signup",
        "/forgot-password",
        "/reset-password",
      ],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
