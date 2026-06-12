import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Inter, Noto_Naskh_Arabic } from "next/font/google";

// Self-host the marketing fonts via next/font. This eliminates:
//   - render-blocking <link> to fonts.googleapis.com (TTFB win)
//   - FOIT / layout shift on the Arabic subtitle (CLS win)
//   - the "Noto Naskh Arabic" Tailwind reference resolving to a system
//     fallback (it wasn't actually loading before).
// `display: "swap"` shows fallback text immediately, then swaps when the
// font arrives — keeps LCP fast.
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const notoArabic = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  display: "swap",
  variable: "--font-arabic",
  weight: ["400", "600", "700"],
});

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
  process.env.NEXT_PUBLIC_SITE_URL || "https://faceless-lab.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Faceless Lab — AI Arabic horror shorts + AI songs | فيديوهات رعب وأغاني بالذكاء الاصطناعي",
    template: "%s · Faceless Lab",
  },
  description:
    "Generate cinematic Arabic horror Shorts AND original Arabic songs with AI. Horror: 6 dialects, free script preview, per-clip reroll, refund on failure. Songs: Suno V5 vocals, lyric-aware cover art, shareable music videos. أنشئ فيديوهات رعب وأغاني عربية احترافية.",
  keywords: [
    // Horror — existing
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
    // Songs — new
    "AI Arabic song generator",
    "Suno Arabic",
    "AI music Arabic",
    "Arabic ballad AI",
    "مولد أغاني بالذكاء الاصطناعي",
    "أغاني عربية AI",
    "ذكاء اصطناعي موسيقى",
    "AI music video Arabic",
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
    siteName: "Faceless Lab",
    title: "Faceless Lab — AI Arabic horror shorts + AI songs",
    description:
      "Two modes, one studio. Generate full Arabic horror shorts from one sentence, or an AI-sung Arabic song with cover art from a theme. اكتب جملة، احصل على فيلم قصير. اكتب فكرة، احصل على أغنية كاملة.",
    locale: "ar_SA",
  },
  twitter: {
    // Same — twitter card pulls from app/opengraph-image.tsx automatically.
    card: "summary_large_image",
    title: "Faceless Lab — AI Arabic horror shorts + AI songs",
    description:
      "Two modes, one studio. Arabic horror shorts AND AI-sung Arabic songs. Free draft, pay only when you generate.",
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

// Viewport + theme-color split out of `metadata` per Next.js 15 contract.
// `viewport` was the missing meta tag that flagged Lighthouse's "Does
// not have a <meta name=viewport>" audit (mobile-friendly + a11y).
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0A0E1A",
  colorScheme: "dark",
};

const softwareApplicationLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Faceless Lab",
  "applicationCategory": "MultimediaApplication",
  "operatingSystem": "Web, iOS, Android",
  "description":
    "AI Arabic content studio with two modes: (1) Horror Shorts — turn a one-line premise into a full cinematic Arabic short with native dialect dialogue, locked character identity across clips, and per-clip refund on failure. (2) AI Songs — generate full Arabic songs with Suno V5 vocals and lyric-aware AI cover art, with sharable music-video output.",
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
    // Horror mode
    "AI Arabic script writer (6 dialects: MSA, Syrian, Egyptian, Khaliji, Maghrebi, Iraqi)",
    "Free script preview before any paid render",
    "Per-clip reroll — regenerate one bad clip without paying for the whole video",
    "Automatic refund if a render fails",
    "Character identity locked across clips via reference image",
    "Native Arabic dialogue with lip-synced audio",
    "9:16 vertical export ready for TikTok, YouTube Shorts, Instagram Reels",
    // Songs mode
    "AI Arabic song generator powered by Suno V5",
    "Lyric-aware AI cover art via Flux Kontext Max",
    "Voice persona save & reuse — keep the same singer across multiple songs",
    "Free lyrics + cover-prompt draft before any paid generation",
    "Square 1:1 music-video export with karaoke-style lyric reveal on the shareable page",
    "Take A / Take B swap — pick the better Suno vocal take, free re-assemble",
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
          "Those are general-purpose tools. Faceless Lab is Arabic-first: the script writer is tuned for Arabic horror, character identity persists across clips, and the audio is genuine Arabic dialect — not English translated. Pricing is also clip-by-clip refundable, not all-or-nothing.",
      },
    },
    {
      "@type": "Question",
      "name": "Can I generate Arabic songs too?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Yes. Faceless Lab has a second mode that generates a full Arabic song from a theme and style. Suno V5 produces the vocals; Flux Kontext Max produces a matching album cover. You get a 1:1 music video with karaoke-style lyric reveal on the share page, ready for WhatsApp and Instagram. Voice personas let you keep the same singer across future songs.",
      },
    },
    {
      "@type": "Question",
      "name": "How much does a song cost?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "About 1 credit per song. The cost is approximately equal to one horror video clip, so the same monthly subscription covers both modes. Drafts (lyrics + cover prompt) are free; you only pay when you approve the full generation.",
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
    <html lang="en" className={`${inter.variable} ${notoArabic.variable}`}>
      <head>
        {/* Preconnect to the Mixkit CDN that serves every background
            video. Saves the DNS + TLS round-trip when the hero video
            (and downstream lazy clips) start fetching — measurable LCP
            win on mobile networks. */}
        <link rel="preconnect" href="https://assets.mixkit.co" crossOrigin="" />
        <link rel="dns-prefetch" href="https://assets.mixkit.co" />
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
      <body className="bg-bg text-ink antialiased font-sans">{children}</body>
    </html>
  );
}
