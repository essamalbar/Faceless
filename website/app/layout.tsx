import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Inter, Noto_Naskh_Arabic, Fraunces } from "next/font/google";

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

// Editorial serif for lyric-like display headlines. Variable font (weight +
// optical size) — loaded once, used with restraint on the landing page.
const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
});

// ---------------------------------------------------------------------------
// SEO METADATA
//
// Goals:
//   1. Win Arabic search intent (the actual market) — Arabic queries are
//      the load-bearing audience and there are no real competitors yet.
//   2. Surface the differentiators that matter for songs:
//        - free lyric draft before payment
//        - pay only when you love the finished song
//        - matching AI cover art for every track
//        - Arabic-first vocals across dialects and styles
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
    default: "Faceless Lab — Turn a feeling into a song | أنشئ أغنية عربية بالذكاء الاصطناعي",
    template: "%s · Faceless Lab",
  },
  description:
    "Describe a theme or a feeling and get a complete original Arabic song — real vocals, written lyrics, and album art — in minutes. No instruments, no studio. Free draft first; pay only when you love it. اكتب فكرة، واحصل على أغنية عربية كاملة.",
  keywords: [
    "AI Arabic song generator",
    "create Arabic song with AI",
    "AI music Arabic",
    "Arabic song maker",
    "original Arabic songs AI",
    "AI singer Arabic",
    "Arabic ballad AI",
    "turn lyrics into a song",
    "مولد أغاني بالذكاء الاصطناعي",
    "إنشاء أغنية عربية",
    "أغاني عربية بالذكاء الاصطناعي",
    "اصنع أغنية",
    "ذكاء اصطناعي موسيقى عربية",
    "كتابة أغنية",
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
    title: "Faceless Lab — Turn a feeling into a song",
    description:
      "Describe a theme and get a full original Arabic song — vocals, lyrics, and album art. Free draft first; pay only when you love it. اكتب فكرة، واحصل على أغنية كاملة.",
    locale: "ar_SA",
  },
  twitter: {
    // Same — twitter card pulls from app/opengraph-image.tsx automatically.
    card: "summary_large_image",
    title: "Faceless Lab — Turn a feeling into a song",
    description:
      "AI-composed original Arabic songs from a single idea — vocals, lyrics, and cover art. Free draft, pay only when you love it.",
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
    "An AI Arabic song studio. Describe a theme or a feeling and get a complete original Arabic song — real vocals, written lyrics, and matching album art — in minutes. Draft the lyrics free; pay only when you approve the full song. Share it as a song page anywhere.",
  "offers": [
    { "@type": "Offer", "name": "Silver", "price": "9", "priceCurrency": "USD", "description": "12 credits / month" },
    { "@type": "Offer", "name": "Gold", "price": "29", "priceCurrency": "USD", "description": "60 credits / month — recommended" },
    { "@type": "Offer", "name": "Platinum", "price": "79", "priceCurrency": "USD", "description": "200 credits / month" },
  ],
  "featureList": [
    "Turn a theme or feeling into a complete original Arabic song",
    "Real sung vocals — no instruments or studio needed",
    "Written Arabic lyrics you can preview and refine for free",
    "Matching album cover art generated for every song",
    "A shareable song page with a lyric reveal — send it anywhere",
    "Save a voice so the same singer carries across your songs",
    "Pay only when you love it — drafting lyrics is always free",
  ],
};

const faqLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What does Faceless Lab do?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "You describe a theme, a mood, or a few lines, and Faceless Lab writes and performs a complete original Arabic song — vocals, lyrics, and a matching album cover — in minutes. No instruments or studio needed.",
      },
    },
    {
      "@type": "Question",
      "name": "Do I need to know music?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "No. If you can describe a feeling in a sentence, you can make a song. You review the written lyrics for free, then generate the full sung track when you're happy with them.",
      },
    },
    {
      "@type": "Question",
      "name": "Can I try it before paying?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Yes. Writing the lyrics is always free. You only spend a credit when you approve the full song — so you pay only for songs you love.",
      },
    },
    {
      "@type": "Question",
      "name": "Is the song mine?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "You own the songs you generate. You get the audio, the lyrics, the cover art, and a shareable song page you can post anywhere.",
      },
    },
    {
      "@type": "Question",
      "name": "How much does it cost?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Plans start at $9/month (Silver, 12 credits). Gold is $29 (60 credits) and Platinum is $79 (200 credits). One credit makes one song, and drafting the lyrics is free.",
      },
    },
    {
      "@type": "Question",
      "name": "Which Arabic styles are supported?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text":
          "Faceless Lab is Arabic-first and handles a range of styles and dialects — from classical and ballad to modern pop — matching the words and the delivery to the mood you choose.",
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
    <html lang="en" className={`${inter.variable} ${notoArabic.variable} ${fraunces.variable}`}>
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
      <body className="bg-bg text-ink antialiased font-sans">{children}</body>
    </html>
  );
}
