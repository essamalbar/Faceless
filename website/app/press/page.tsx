import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Download,
  ImageIcon,
  Type,
  Layers,
  Mail,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";

// ----------------------------------------------------------------------------
// PRESS KIT — /press
//
// Server Component. Lives next to /about as a sibling marketing route.
// Same visual grammar as the home page (eyebrow + dual-language title +
// card grid + gold CTA) so the brand stays continuous.
//
// NOTE: the three /press/*.zip asset links are intentional stubs — the
// actual ZIP files haven't been produced yet. The link targets exist so
// we can drop the assets into website/public/press/ later without
// touching this template.
// ----------------------------------------------------------------------------

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "https://app.faceless-lab.com";
const PRESS_EMAIL = "press@faceless-lab.com";

export const metadata: Metadata = {
  title: "Press Kit — Resources for journalists & creators",
  description:
    "Press kit for Faceless Lab — brand boilerplate, downloadable logo + icon + screenshot assets, key facts, and a direct contact for journalists writing about the Arabic AI studio.",
  openGraph: {
    type: "website",
    title: "Press Kit — Faceless Lab",
    description:
      "Brand assets, key facts, and press contact for Faceless Lab, the Arabic-first AI song studio.",
    url: "/press",
  },
  twitter: {
    card: "summary_large_image",
    title: "Press Kit — Faceless Lab",
    description:
      "Brand assets and press contact for Faceless Lab — the Arabic AI studio.",
  },
  alternates: { canonical: "/press" },
};

export default function PressPage() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip">
      <SimpleNav />
      <Hero />
      <Boilerplate />
      <BrandAssets />
      <KeyFacts />
      <PressContact />
      <SimpleFooter />
    </main>
  );
}

function SimpleNav() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-bg/85 border-b border-white/[0.06]">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center">
        <Link href="/" className="flex items-center gap-2.5">
          <SparkleLogo size={28} />
          <span className="font-semibold text-[15px] tracking-tight">
            Faceless Lab
          </span>
        </Link>
        <nav className="hidden md:flex items-center gap-7 ml-12 text-[13px] text-muted">
          <Link href="/" className="hover:text-ink transition-colors">Home</Link>
          <Link href="/about" className="hover:text-ink transition-colors">About</Link>
          <Link href="/press" className="text-ink transition-colors">Press</Link>
        </nav>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <a
            href={`${APP_URL}/`}
            className="text-[13px] text-muted hover:text-ink px-3 py-2"
          >
            Sign in
          </a>
          <a
            href={`${APP_URL}/`}
            className="bg-accent text-bg font-semibold text-[13px] px-4 py-2 rounded-md hover:bg-accent/90 transition-colors"
          >
            Start free
          </a>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative pt-40 pb-20 sm:pt-48 sm:pb-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-4xl mx-auto">
        <SectionEyebrow text="PRESS KIT" />
        <h1 className="text-[44px] sm:text-6xl lg:text-7xl font-semibold tracking-[-0.04em] leading-[1.02] mb-8">
          Resources for{" "}
          <span className="bg-gradient-to-br from-accent via-amber-200 to-accent2 bg-clip-text text-transparent">
            journalists &amp; creators.
          </span>
        </h1>
        <p className="text-lg sm:text-xl text-ink/85 leading-relaxed max-w-2xl">
          Everything you need to write about Faceless Lab: boilerplate,
          downloadable brand assets, founder facts, and a direct contact.
        </p>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// BOILERPLATE — paste-ready paragraph for press articles.
// ----------------------------------------------------------------------------
function Boilerplate() {
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-4xl mx-auto">
        <SectionEyebrow text="ABOUT THE COMPANY" />
        <SectionTitle en="One paragraph, ready to paste." ar="فقرة جاهزة للنسخ" />
        <div className="mt-10 bg-white/[0.02] border border-white/10 rounded-2xl p-7 sm:p-9">
          <p className="text-[15px] sm:text-base text-ink/90 leading-relaxed">
            Faceless Lab is an Arabic-first AI song studio. From a single
            Arabic sentence — a theme, a feeling, a memory — the platform
            drafts full lyrics in one of six dialects, then performs them as a
            complete original song with real sung vocals and matching cover
            art. Drafting the lyrics is free; users pay a single credit only
            when they approve the finished song, and a credit is returned
            automatically if a song fails to generate. Founded in 2026 by
            Essam and headquartered in Dubai, Faceless Lab targets the Arabic
            creator economy that has been chronically underserved by
            general-purpose AI tools.
          </p>
        </div>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// BRAND ASSETS — three downloadable bundles. ZIPs don't exist yet; links
// will 404 until the assets are dropped into website/public/press/.
// ----------------------------------------------------------------------------
function BrandAssets() {
  const assets = [
    {
      icon: Type,
      title: "Wordmark logo",
      blurb: "PNG, 2400×800, dark + light variants.",
      href: "/press/faceless-lab-wordmark.zip",
    },
    {
      icon: ImageIcon,
      title: "App icon",
      blurb: "SVG vector + PNG raster at 1024×1024.",
      href: "/press/faceless-lab-icon.zip",
    },
    {
      icon: Layers,
      title: "Screenshot pack",
      blurb: "Four shots — home, lyrics, cover art, share.",
      href: "/press/faceless-lab-screenshots.zip",
    },
  ];
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-6xl mx-auto">
        <SectionEyebrow text="BRAND ASSETS" />
        <SectionTitle en="Logo, icon, screenshots." ar="الشعار والأيقونة ولقطات الشاشة" />
        <p className="mt-4 text-muted max-w-2xl">
          Use these freely in editorial coverage. Don&apos;t alter the gold
          gradient on the wordmark, and please credit &quot;Faceless Lab&quot;
          on first mention.
        </p>
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-4">
          {assets.map((a) => (
            <div
              key={a.title}
              className="bg-white/[0.02] border border-white/10 rounded-2xl p-7 hover:bg-white/[0.04] hover:border-white/20 transition-colors flex flex-col"
            >
              <div className="w-11 h-11 rounded-xl bg-accent/10 border border-accent/25 flex items-center justify-center mb-5">
                <a.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="text-lg font-semibold mb-2 tracking-tight">
                {a.title}
              </h3>
              <p className="text-[13px] text-muted leading-relaxed mb-6 flex-1">
                {a.blurb}
              </p>
              <a
                href={a.href}
                download
                className="inline-flex items-center justify-center gap-2 bg-accent text-bg font-semibold text-[13px] px-4 py-2.5 rounded-md hover:bg-accent/90 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Download
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// KEY FACTS — 5 one-liners journalists tend to fact-check.
// ----------------------------------------------------------------------------
function KeyFacts() {
  const facts = [
    { label: "Founded", value: "2026" },
    { label: "Founder", value: "Essam — based in the UAE" },
    { label: "Headquarters", value: "Dubai, United Arab Emirates" },
    {
      label: "Languages supported",
      value: "Modern Standard Arabic + 5 dialects (Syrian, Egyptian, Khaliji, Maghrebi, Iraqi)",
    },
    {
      label: "Tech stack",
      value: "State-of-the-art AI vocal and image models, behind a proprietary Arabic-first lyric-and-song pipeline",
    },
  ];
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-4xl mx-auto">
        <SectionEyebrow text="KEY FACTS" />
        <SectionTitle en="The basics." ar="المعلومات الأساسية" />
        <dl className="mt-12 divide-y divide-white/[0.06] border-y border-white/[0.06]">
          {facts.map((f) => (
            <div
              key={f.label}
              className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-6 py-5"
            >
              <dt className="text-[11px] font-bold text-accent tracking-[0.18em] uppercase pt-1">
                {f.label}
              </dt>
              <dd className="sm:col-span-2 text-[15px] text-ink/90 leading-relaxed">
                {f.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// PRESS CONTACT — single named contact + big mailto pill.
// ----------------------------------------------------------------------------
function PressContact() {
  return (
    <section className="relative py-24 sm:py-28 px-5 sm:px-8">
      <div className="max-w-2xl mx-auto text-center">
        <div className="inline-flex justify-center mb-7">
          <SparkleLogo size={48} />
        </div>
        <SectionEyebrow text="PRESS CONTACT" />
        <h2 className="mt-2 text-3xl sm:text-5xl font-semibold tracking-[-0.035em] mb-3">
          Talk to Essam directly.
        </h2>
        <p className="text-base text-muted max-w-md mx-auto mb-9">
          Working on a story? Need a quote, an interview, or a higher-res
          asset? Email us — we reply the same day.
        </p>
        <a
          href={`mailto:${PRESS_EMAIL}?subject=Press%20inquiry%20%E2%80%94%20Faceless%20Lab`}
          className="inline-flex items-center gap-2 bg-accent text-bg font-semibold text-base px-7 py-3.5 rounded-lg hover:bg-accent/90 transition-colors shadow-xl shadow-accent/20"
        >
          <Mail className="w-4 h-4" />
          {PRESS_EMAIL}
          <ArrowRight className="w-4 h-4" />
        </a>
      </div>
    </section>
  );
}

function SimpleFooter() {
  return (
    <footer className="border-t border-white/[0.06] py-10 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center gap-5">
        <div className="flex items-center gap-2.5">
          <SparkleLogo size={22} />
          <span className="text-[13px] text-muted">
            Faceless Lab · faceless-lab.com
          </span>
        </div>
        <div className="sm:ml-auto flex items-center gap-6 text-[13px] text-muted">
          <Link href="/" className="hover:text-ink transition-colors">Home</Link>
          <Link href="/about" className="hover:text-ink transition-colors">About</Link>
          <Link href="/press" className="hover:text-ink transition-colors">Press</Link>
          <a href={`${APP_URL}/`} className="hover:text-ink transition-colors">Sign in</a>
        </div>
      </div>
    </footer>
  );
}

// ----------------------------------------------------------------------------
// PRIMITIVES — matched to /about (and visually equivalent to page.tsx,
// minus framer-motion since both new pages are Server Components).
// ----------------------------------------------------------------------------
function SectionEyebrow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="w-8 h-px bg-accent" />
      <span className="text-[10px] font-bold text-accent tracking-[0.22em]">
        {text}
      </span>
    </div>
  );
}

function SectionTitle({ en, ar }: { en: string; ar: string }) {
  return (
    <h2 className="text-3xl sm:text-5xl lg:text-6xl font-semibold tracking-[-0.03em] leading-tight">
      {en}
      <span
        className="ml-3 text-muted/60 text-xl sm:text-2xl font-normal font-arabic"
        dir="rtl"
      >
        {ar}
      </span>
    </h2>
  );
}
