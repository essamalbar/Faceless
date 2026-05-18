// Auto-generated robots.txt. Next.js App Router serves this at /robots.txt.
// Open to all crawlers; only the API surface is disallowed (it's on a
// separate origin anyway, but explicit is cheap).

import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://faceless-kappa.vercel.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/"],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
