import "./globals.css";
import type { Metadata } from "next";

// ---------------------------------------------------------------------------
// SEO METADATA
//
// Goals:
//   1. Win Arabic search intent (the actual market) — Arabic queries are
//      the load-bearing audience and there are no real competitors yet.
//   2. Surface the four differentiators that competitors LACK:
//        - free script preview before payment
//        - per-clip reroll instead of all-or-nothing
//        - refund on render failure
//        - 6 Arabic dialects
//   3. Self-describe as a SoftwareApplication via JSON-LD so Google can
//      build a rich result with pricing + rating.
//
// Notes:
//   - keep <html lang="en"> for now; Arabic content is mixed inline with
//      `dir="rtl"` blocks. A full /ar/* tree is a follow-up — not needed
//      to rank for Arabic queries since title/description/keywords + body
//      Arabic content are the strongest signals.
//   - JSON-LD goes in <head> via raw <script>; Next.js's official guidance
//      for App Router. No client-side hydration needed (it's plain JSON).
// ---------------------------------------------------------------------------

// Production URL — Vercel auto-deploy from main lives at the *.vercel.app
// preview domain. Override via NEXT_PUBLIC_SITE_URL once a custom domain
// (e.g. faceless.binghatti.com) is mapped in Vercel.
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://faceless-kappa.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Faceless — AI Arabic horror video generator | فيديوهات رعب بالعربي",
    template: "%s · Faceless",
  },
  description:
    "Generate cinematic Arabic horror Shorts from one sentence. 6 dialects (Syrian, Egyptian, Khaliji, MSA, Maghrebi, Iraqi). Free script preview. Per-clip reroll. Refund on failure. أنشئ فيديوهات رعب عربية احترافية من جملة واحدة.",
  keywords: [
    "Arabic AI video",
    "Arabic horror shorts",
    "AI video generator",
    "Veo Arabic",
    "Arabic Shorts maker",
    "TikTok Arabic AI",
    "YouTube Shorts Arabic",
    "فيديو رعب بالذكاء الاصطناعي",
    "إنشاء فيديو عربي",
    "مولد فيديو رعب",
    "فيديوهات تيك توك بالعربي",
    "ذكاء اصطناعي فيديو عربي",
    "صانع فيديوهات قصيرة",
    "Veo3 Arabic",
    "Kling Arabic horror",
  ],
  alternates: {
    canonical: SITE_URL,
    languages: {
      "ar": SITE_URL,
      "en": SITE_URL,
      "x-default": SITE_URL,
    },
  },
  openGraph: {
    // OG image auto-detected from app/opengraph-image.tsx — Next.js
    // serves the rendered PNG at /opengraph-image with the right
    // dimensions + alt text from that file's exports. Don't list
    // it here or we'll override the auto-detection.
    type: "website",
    url: SITE_URL,
    siteName: "Faceless",
    title: "Faceless — AI Arabic horror shorts",
    description:
      "One sentence → full Arabic horror short. Script free, render-on-demand. 6 dialects. Refund on failure. اكتب جملة، احصل على فيلم قصير كامل.",
    locale: "ar_SA",
  },
  twitter: {
    // Same — twitter card pulls from app/opengraph-image.tsx automatically.
    card: "summary_large_image",
    title: "Faceless — AI Arabic horror shorts",
    description:
      "Write one sentence → get a full Arabic horror short. Free preview, refund on failure.",
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
  // Domain ownership verification. Token is intentionally a public
  // value — Google publishes it in our HTML by design, so hardcoding
  // is fine. Env var override exists for future re-issuance without a
  // redeploy.
  verification: {
    google:
      process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION ||
      "dDBMtUULMhsbyUW7DJxCx43ffaHo_unJxIf91VQmHhE",
  },
  category: "technology",
};

const softwareApplicationLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Faceless",
  "applicationCategory": "MultimediaApplication",
  "operatingSystem": "Web, iOS, Android",
  "description":
    "AI Arabic horror Shorts generator. Turn a one-line premise into a full cinematic Arabic short with native dialect dialogue, locked character identity across clips, and per-clip refund on failure.",
  "offers": [
    {
      "@type": "Offer",
      "name": "Starter",
      "price": "9",
      "priceCurrency": "USD",
      "description": "12 video clips / month",
    },
    {
      "@type": "Offer",
      "name": "Creator",
      "price": "29",
      "priceCurrency": "USD",
      "description": "60 video clips / month — recommended",
    },
    {
      "@type": "Offer",
      "name": "Pro",
      "price": "79",
      "priceCurrency": "USD",
      "description": "200 video clips / month",
    },
  ],
  "featureList": [
    "AI Arabic script writer (6 dialects: MSA, Syrian, Egyptian, Khaliji, Maghrebi, Iraqi)",
    "Free script preview before any paid render",
    "Per-clip reroll — regenerate one bad clip without paying for the whole video",
    "Automatic refund if a render fails",
    "Character identity locked across clips via reference image",
    "Native Arabic dialogue with lip-synced audio",
    "9:16 vertical export ready for TikTok, YouTube Shorts, Instagram Reels",
  ],
};

const faqLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Do I pay if the render fails?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "No. Every credit charged against a failed render is refunded automatically. You only pay for clips that successfully deliver.",
      },
    },
    {
      "@type": "Question",
      "name": "Can I preview the script before paying?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Yes. Script generation is always free. You write a one-line premise, the AI produces a full Arabic script with characters, dialogue, and shot directions, then you decide whether to render. Subscribe only when you're ready to pay for the rendered video.",
      },
    },
    {
      "@type": "Question",
      "name": "What if just one clip looks wrong?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Reroll only that clip. You pay for one clip, not the whole video. Most competitors force you to re-render everything from scratch.",
      },
    },
    {
      "@type": "Question",
      "name": "Which Arabic dialects are supported?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Six dialects: Modern Standard Arabic (MSA / فصحى), Syrian (شامي), Egyptian (مصري), Khaliji (خليجي), Maghrebi (مغاربي), and Iraqi (عراقي). The script writer matches both vocabulary and rhythm to the dialect you pick.",
      },
    },
    {
      "@type": "Question",
      "name": "Can I publish to TikTok and YouTube?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Yes. Every render is 9:16 vertical (1080×1920) with native audio and burned-in Arabic captions — ready to upload to TikTok, YouTube Shorts, and Instagram Reels. Direct-publish integrations are on the roadmap.",
      },
    },
    {
      "@type": "Question",
      "name": "What's the difference vs Sora, Veo, or Runway?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Those are general-purpose tools. Faceless is Arabic-first: the script writer is tuned for Arabic horror, character identity persists across clips, and the audio is genuine Arabic dialect — not English translated. Pricing is also clip-by-clip refundable, not all-or-nothing.",
      },
    },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="alternate"
          type="application/rss+xml"
          title="Faceless — Latest Stories"
          href="/rss.xml"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(softwareApplicationLd),
          }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
        />
      </head>
      <body className="bg-bg text-ink antialiased">{children}</body>
    </html>
  );
}
