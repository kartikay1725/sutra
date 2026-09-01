import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://sutra.dev";

  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/about"],
      disallow: ["/api/", "/repositories/", "/agents/", "/changes/", "/pull-requests/", "/ci/", "/tasks/"],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
