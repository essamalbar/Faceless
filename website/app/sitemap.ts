// Auto-generated sitemap. Next.js App Router serves this at /sitemap.xml.
// We expose the marketing page + every theme/dialect anchor so search
// engines can index the long-tail keyword pages. When we add /v/{slug}
// public showcase pages, list them here too.

import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://faceless-kappa.vercel.app";

const themes = ["folkloric", "memory", "wilderness", "urban", "domestic", "travel"];
const dialects = ["msa", "syrian", "egyptian", "khaliji", "maghrebi", "iraqi"];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const home: MetadataRoute.Sitemap[number] = {
    url: SITE,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 1.0,
  };

  // Anchor URLs let search engines understand the section structure
  // (and give us featured snippets for "AI Arabic horror templates" etc).
  const sections: MetadataRoute.Sitemap = [
    "#templates", "#showreel", "#features", "#pricing",
  ].map((hash) => ({
    url: `${SITE}/${hash}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.6,
  }));

  // Each theme + dialect combo is a long-tail keyword we can rank for
  // (e.g. "AI Arabic horror folkloric Egyptian"). We don't have dedicated
  // pages yet — these are anchored to the templates section, but the
  // query string lets us prefill the app for that specific combo.
  const longtail: MetadataRoute.Sitemap = [];
  for (const theme of themes) {
    for (const dialect of dialects) {
      longtail.push({
        url: `${SITE}/?theme=${theme}&dialect=${dialect}`,
        lastModified: now,
        changeFrequency: "monthly",
        priority: 0.4,
      });
    }
  }

  return [home, ...sections, ...longtail];
}
