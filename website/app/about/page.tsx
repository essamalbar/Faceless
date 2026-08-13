import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";

// ----------------------------------------------------------------------------
// ABOUT PAGE — /about
//
// Server Component (no client interactivity). Matches the landing-page
// dark/gold aesthetic but drops the heavy framer-motion choreography:
// this page is read, not scrolled-through. Composition mirrors page.tsx
// section primitives (SectionEyebrow + h2 sizing) so the brand feels
// continuous between routes.
// ----------------------------------------------------------------------------

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "https://app.faceless-lab.com";

export const metadata: Metadata = {
  title: "About — An Arabic AI song studio, built by an Arab",
  description:
    "Faceless Lab is an Arabic-first AI song studio, built because the big general-purpose AI tools treat Arabic as a translation afterthought. Turn one line of Arabic into a full original song. Founded by Essam in Dubai.",
  openGraph: {
    type: "article",
    title: "About Faceless Lab — An Arabic AI song studio, built by an Arab",
    description:
      "Why Faceless Lab exists, what the song studio does in plain language, and a founder note from Essam.",
    url: "/about",
  },
  twitter: {
    card: "summary_large_image",
    title: "About Faceless Lab — An Arabic AI song studio, built by an Arab",
    description:
      "An Arabic-first AI song studio. Built by Essam.",
  },
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip">
      <SimpleNav />
      <Hero />
      <WhyExist />
      <Product />
      <Principles />
      <FounderNote />
      <FooterCTA />
      <SimpleFooter />
    </main>
  );
}

// ----------------------------------------------------------------------------
// NAV — static (no scroll listener) version of the landing-page nav. Same
// height, same brand mark, same Start-free pill so visitors landing here
// from social can convert without going back to the home page.
// ----------------------------------------------------------------------------
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
          <Link href="/about" className="text-ink transition-colors">About</Link>
          <Link href="/press" className="hover:text-ink transition-colors">Press</Link>
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

// ----------------------------------------------------------------------------
// HERO — short eyebrow + big headline + 2-3 sentence sub. Reads calm, not
// theatrical — About is read, not scrolled-through.
// ----------------------------------------------------------------------------
function Hero() {
  return (
    <section className="relative pt-40 pb-20 sm:pt-48 sm:pb-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-4xl mx-auto">
        <SectionEyebrow text="ABOUT FACELESS LAB" />
        <h1 className="text-[44px] sm:text-6xl lg:text-7xl font-semibold tracking-[-0.04em] leading-[1.02] mb-8">
          An Arabic AI song studio,{" "}
          <span className="bg-gradient-to-br from-accent via-amber-200 to-accent2 bg-clip-text text-transparent">
            built by an Arab.
          </span>
        </h1>
        <p className="text-lg sm:text-xl text-ink/85 leading-relaxed max-w-2xl">
          Faceless Lab turns one line of Arabic into a full original song —
          real sung vocals, written lyrics, and matching cover art. It exists
          because the big general-purpose AI tools weren&apos;t built with
          Arabic in mind — and that gap was big enough to be a company.
        </p>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// WHY WE EXIST — the gap. Keep it specific (name the failure modes, not the
// vendors) so the argument doesn't sound generic.
// ----------------------------------------------------------------------------
function WhyExist() {
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-4xl mx-auto">
        <SectionEyebrow text="WHY WE EXIST" />
        <SectionTitle en="The gap nobody was filling." ar="الفجوة التي لم يملأها أحد" />
        <div className="mt-10 space-y-5 text-[15px] sm:text-base text-ink/85 leading-relaxed max-w-2xl">
          <p>
            The big general-purpose AI music tools treat Arabic as an
            afterthought. Lyrics arrive translation-shaped — written in an
            English rhythm and bent into Arabic words. Dialects get flattened;
            everything ends up in the same stiff, formal register. The writing
            tradition that gave the Arab world its songs is nowhere in the
            model.
          </p>
          <p>
            That isn&apos;t a small bug — it&apos;s a missing layer. The result
            is music that looks Arabic but reads like a costume on top of an
            American skeleton.
          </p>
          <p>
            Faceless Lab is that layer. We write the Arabic lyrics first, in
            the dialect and register you ask for. We shape the vocal delivery
            to fit the feeling. We build the song around the language — not the
            language around the song.
          </p>
        </div>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// THE PRODUCT — two facets of one song, in plain language: the lyrics and
// the voice. Two cards keep visual parity with the rest of the site.
// ----------------------------------------------------------------------------
function Product() {
  const facets = [
    {
      eyebrow: "THE LYRICS",
      title: "Written, not translated",
      ar: "كلمات مكتوبة لا مترجمة",
      body:
        "Write one line — a theme, a feeling, a memory — and we draft full Arabic lyrics for free, in the dialect and register you choose. Read them, refine them, and only keep going when the words feel right. Nothing is routed through English on the way.",
    },
    {
      eyebrow: "THE VOICE",
      title: "Sung into a full song",
      ar: "أداء غنائي كامل",
      body:
        "Approved lyrics become a complete original song — real sung vocals with matching cover art and a shareable song page. Save a voice so the same singer carries across your tracks. You spend a single credit only when you approve the finished song.",
    },
  ];
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-5xl mx-auto">
        <SectionEyebrow text="THE PRODUCT" />
        <SectionTitle en="In plain language." ar="بكلام بسيط" />
        <div className="mt-14 grid grid-cols-1 md:grid-cols-2 gap-4">
          {facets.map((m) => (
            <div
              key={m.title}
              className="bg-gradient-to-br from-accent/[0.05] to-transparent border border-accent/20 rounded-2xl p-7"
            >
              <div className="text-[10px] font-bold text-accent tracking-[0.22em] mb-3">
                {m.eyebrow}
              </div>
              <h3 className="text-2xl font-semibold mb-1 tracking-tight">
                {m.title}
              </h3>
              <div
                className="text-[13px] text-muted/80 mb-4 font-arabic"
                dir="rtl"
              >
                {m.ar}
              </div>
              <p className="text-[14px] text-ink/85 leading-relaxed">
                {m.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// PRINCIPLES — 4 short bullets. These map to the pricing-page guarantees
// but framed as values, not features.
// ----------------------------------------------------------------------------
function Principles() {
  const principles = [
    {
      title: "Pay only for what you love.",
      body:
        "Drafting lyrics is always free. You spend a single credit only when you approve the finished song — never on a draft you didn't keep.",
    },
    {
      title: "Arabic-first, not Arabic-translated.",
      body:
        "Lyrics are written in Arabic from your prompt, in the dialect you choose. Nothing is translated through English on the way.",
    },
    {
      title: "The song is yours.",
      body:
        "You keep the words, the vocals, the cover art, and the shareable song page. We just hold the rails that get you there.",
    },
    {
      title: "Refund if we fail.",
      body:
        "Every credit is recoverable. If a song fails to generate, the credit returns automatically — you never have to ask.",
    },
  ];
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-5xl mx-auto">
        <SectionEyebrow text="WHAT WE BELIEVE" />
        <SectionTitle en="Four rules we won't bend." ar="أربع قواعد لا نتنازل عنها" />
        <ul className="mt-14 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {principles.map((p) => (
            <li
              key={p.title}
              className="bg-white/[0.02] border border-white/10 rounded-xl p-6 hover:bg-white/[0.04] hover:border-white/20 transition-colors"
            >
              <h3 className="text-[16px] font-semibold mb-2 tracking-tight text-ink">
                {p.title}
              </h3>
              <p className="text-[13px] text-muted leading-relaxed">
                {p.body}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// FOUNDER NOTE — Essam, first-person, ~120 words. Plain quote block; no
// portrait yet (asset workstream lives in /press).
// ----------------------------------------------------------------------------
function FounderNote() {
  return (
    <section className="relative py-24 px-5 sm:px-8 border-b border-white/[0.05]">
      <div className="max-w-3xl mx-auto">
        <SectionEyebrow text="FOUNDER NOTE" />
        <SectionTitle en="From Essam." ar="من عصام" />
        <blockquote className="mt-12 relative pl-6 sm:pl-8 border-l-2 border-accent/40">
          <p className="text-[17px] sm:text-lg text-ink/90 leading-relaxed mb-5">
            I built this because every time I tried to make Arabic music with
            the big general-purpose AI tools, the result was a translated
            American skeleton wearing an Arabic costume. The lyrics were wrong.
            The dialects were flattened. The feeling never survived the
            translation.
          </p>
          <p className="text-[17px] sm:text-lg text-ink/90 leading-relaxed mb-5">
            Faceless Lab is what I wished existed: an Arabic-first studio that
            writes the lyrics in your dialect, sings them into a full song, and
            lets you read the words before you ever pay. One line in — a
            complete Arabic song out.
          </p>
          <footer className="text-sm text-muted">
            — Essam, founder. Dubai, UAE.
          </footer>
        </blockquote>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// FOOTER CTA — gold pill, identical pattern to landing-page FinalCTA.
// ----------------------------------------------------------------------------
function FooterCTA() {
  return (
    <section className="relative py-24 sm:py-28 px-5 sm:px-8">
      <div className="max-w-2xl mx-auto text-center">
        <div className="inline-flex justify-center mb-7">
          <SparkleLogo size={48} />
        </div>
        <h2 className="text-3xl sm:text-5xl font-semibold tracking-[-0.035em] mb-5">
          Try it free.
        </h2>
        <p className="text-base text-muted max-w-md mx-auto mb-9">
          Write one line. Get full Arabic lyrics back. Pay only when you love
          the finished song.
        </p>
        <a
          href={`${APP_URL}/`}
          className="inline-flex items-center gap-2 bg-accent text-bg font-semibold text-base px-7 py-3.5 rounded-lg hover:bg-accent/90 transition-colors shadow-xl shadow-accent/20"
        >
          <Sparkles className="w-4 h-4" />
          Start creating
          <ArrowRight className="w-4 h-4" />
        </a>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// FOOTER — links cross-route now that there are sibling pages.
// ----------------------------------------------------------------------------
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
// PRIMITIVES — duplicated from page.tsx (which is "use client" and so
// can't export its functions to a Server Component). Keep visual parity.
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
