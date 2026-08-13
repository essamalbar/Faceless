"use client";

import {
  motion,
  useScroll,
  useTransform,
  AnimatePresence,
  useReducedMotion,
} from "framer-motion";
import { useRef, useState, useEffect, useMemo } from "react";
import {
  Sparkles, ArrowRight, PenLine, Music4, Share2, Mic2,
  Disc3, Heart, Check, ScrollText, AudioLines,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";
import { SiteFooter } from "@/components/site-chrome";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "https://app.faceless-lab.com";

// ============================================================================
// PAGE — an AI Arabic SONG studio. No video anywhere; no third-party names.
// Signature: a living audio waveform (sound made visible). Editorial serif
// (Fraunces) for lyric-like headlines; warm gold→rose→violet stage-light glow.
// ============================================================================
export default function Page() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip antialiased">
      <Nav />
      <Hero />
      <HowItWorks />
      <WhatYouGet />
      <Showcase />
      <Why />
      <PricingTeaser />
      <FinalCTA />
      <SiteFooter />
    </main>
  );
}

// ----------------------------------------------------------------------------
// NAV
// ----------------------------------------------------------------------------
function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header
      className={`fixed top-0 inset-x-0 z-50 transition-colors duration-300 ${
        scrolled ? "backdrop-blur-xl bg-bg/80 border-b border-white/[0.06]" : "bg-transparent"
      }`}
    >
      <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center">
        <a href="#top" className="flex items-center gap-2.5">
          <SparkleLogo size={28} />
          <span className="font-semibold text-[15px] tracking-tight">Faceless Lab</span>
        </a>
        <nav aria-label="Primary" className="hidden md:flex items-center gap-8 ml-12 text-[13px] text-muted">
          <a href="#how" className="hover:text-ink transition-colors">How it works</a>
          <a href="#songs" className="hover:text-ink transition-colors">Songs</a>
          <a href="/pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href="/about" className="hover:text-ink transition-colors">About</a>
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          <a href={`${APP_URL}/`} className="text-[13px] text-muted hover:text-ink px-3 py-2">Sign in</a>
          <a
            href={`${APP_URL}/`}
            className="text-[13px] font-semibold px-4 py-2 rounded-full text-bg bg-gradient-to-r from-accent via-rose to-accent2 hover:brightness-110 transition"
          >
            Start free
          </a>
        </div>
      </div>
    </header>
  );
}

// ----------------------------------------------------------------------------
// SIGNATURE — living waveform. Deterministic heights (no hydration mismatch);
// a centered bell so the middle rises like a real spectrum.
// ----------------------------------------------------------------------------
function Waveform({ bars = 56, className = "" }: { bars?: number; className?: string }) {
  const reduce = useReducedMotion();
  const items = useMemo(
    () =>
      Array.from({ length: bars }, (_, i) => {
        const bell = Math.exp(-Math.pow((i / (bars - 1) - 0.5) * 2.1, 2));
        const base = (0.16 + 0.84 * Math.abs(Math.sin(i * 0.7) * Math.cos(i * 0.21))) * (0.35 + 0.65 * bell);
        return { base, dur: 0.85 + (i % 6) * 0.14, delay: (i % 13) * 0.055 };
      }),
    [bars],
  );
  return (
    <div className={`flex items-center justify-center gap-[3px] sm:gap-[4px] h-full ${className}`} aria-hidden="true">
      {items.map((b, i) => (
        <motion.span
          key={i}
          className="w-[3px] sm:w-[4px] rounded-full bg-gradient-to-t from-accent2/25 via-rose to-accent"
          style={{ height: "100%", transformOrigin: "center" }}
          initial={{ scaleY: b.base * 0.5 }}
          animate={reduce ? { scaleY: b.base } : { scaleY: [b.base * 0.32, b.base, b.base * 0.5, b.base * 0.88, b.base * 0.4] }}
          transition={reduce ? { duration: 0 } : { duration: b.dur, delay: b.delay, repeat: Infinity, repeatType: "mirror", ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------------
// HERO
// ----------------------------------------------------------------------------
function Hero() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const glowY = useTransform(scrollYProgress, [0, 1], [0, 120]);

  const themes = [
    "a rainy night in Beirut",
    "my mother's kitchen table",
    "the long road back home",
    "falling in love in June",
    "the city that raised me",
    "letting go of an old friend",
  ];
  const [ti, setTi] = useState(0);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    const t = setInterval(() => setTi((x) => (x + 1) % themes.length), 2700);
    return () => clearInterval(t);
  }, [reduce, themes.length]);

  return (
    <section ref={ref} id="top" className="relative overflow-hidden pt-36 pb-24 sm:pt-44 sm:pb-28 px-5 sm:px-8">
      {/* warm stage-light glow */}
      <motion.div style={{ y: glowY }} aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 -translate-x-1/2 -top-20 h-[520px] w-[820px] max-w-[120vw] rounded-full blur-[120px] opacity-40"
             style={{ background: "radial-gradient(ellipse at center, rgba(231,181,60,0.55), rgba(236,143,169,0.35) 42%, rgba(139,92,246,0.28) 68%, transparent 75%)" }} />
      </motion.div>

      <div className="max-w-3xl mx-auto text-center">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-[11px] tracking-[0.14em] text-muted mb-8">
          <AudioLines className="w-3.5 h-3.5 text-rose" />
          AI ARABIC SONG STUDIO
        </motion.div>

        <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.05 }}
          className="font-display font-medium tracking-[-0.02em] leading-[1.02] text-[46px] sm:text-7xl">
          Turn a feeling
          <br />
          into a{" "}
          <span className="italic bg-gradient-to-r from-accent via-rose to-accent2 bg-clip-text text-transparent">song.</span>
        </motion.h1>

        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6, delay: 0.2 }}
          className="font-arabic text-xl sm:text-2xl text-muted/90 mt-5" dir="rtl">
          اكتب فكرة… واسمعها أغنية.
        </motion.p>

        <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.28 }}
          className="text-[15px] sm:text-lg text-muted leading-relaxed max-w-xl mx-auto mt-7">
          Describe a theme, a memory, or a few words. Get a complete original Arabic song —
          real vocals, written lyrics, and cover art — in minutes. No instruments. No studio.
        </motion.p>

        {/* Prompt device — the product's first move, made tangible */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.36 }}
          className="mt-9 max-w-lg mx-auto">
          <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-surface/70 p-2 pl-4 text-left shadow-2xl shadow-black/40">
            <PenLine className="w-4 h-4 text-muted shrink-0" />
            <div className="flex-1 min-w-0 text-[14px] sm:text-[15px] text-ink/90 py-1.5 truncate">
              <span className="text-muted">a song about </span>
              <span className="relative inline-block align-bottom">
                <AnimatePresence mode="wait">
                  <motion.span key={ti} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.35 }}
                    className="bg-gradient-to-r from-accent via-rose to-accent2 bg-clip-text text-transparent font-medium">
                    {themes[ti]}
                  </motion.span>
                </AnimatePresence>
              </span>
            </div>
            <a href={`${APP_URL}/`}
              className="shrink-0 inline-flex items-center gap-1.5 text-[13px] font-semibold px-4 py-2.5 rounded-xl text-bg bg-gradient-to-r from-accent via-rose to-accent2 hover:brightness-110 transition">
              Compose <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>
          <p className="text-[12px] text-muted/70 mt-3">Free to write the lyrics. Pay only when you love the song.</p>
        </motion.div>
      </div>

      {/* signature waveform */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.9, delay: 0.5 }}
        className="max-w-4xl mx-auto mt-16 h-24 sm:h-28 px-2">
        <Waveform />
      </motion.div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// HOW IT WORKS — a true 3-step sequence (write → compose → share)
// ----------------------------------------------------------------------------
function HowItWorks() {
  const steps = [
    { n: "one", icon: PenLine, title: "Write a line", ar: "اكتب",
      body: "Type a theme, a feeling, or a few words. We draft the Arabic lyrics for you — read them, tweak them, all free." },
    { n: "two", icon: Mic2, title: "Hear it composed", ar: "استمع",
      body: "Approve the words and they're sung into a full original Arabic song, with matching album art created to fit the mood." },
    { n: "three", icon: Share2, title: "Share it", ar: "شارك",
      body: "Get the audio and a shareable song page with a lyric reveal — send it to anyone, anywhere." },
  ];
  return (
    <Section id="how" eyebrow="HOW IT WORKS" title="Three steps, no studio." ar="ثلاث خطوات">
      <ol className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-4">
        {steps.map((s, i) => (
          <Reveal key={s.n} delay={i * 0.08}>
            <li className="h-full rounded-2xl border border-white/10 bg-white/[0.02] p-7 hover:border-white/20 hover:bg-white/[0.035] transition-colors">
              <div className="flex items-center justify-between mb-6">
                <span className="font-display italic text-2xl text-muted/50">{s.n}</span>
                <s.icon className="w-5 h-5 text-rose" />
              </div>
              <h3 className="text-lg font-semibold tracking-tight mb-1.5">{s.title}
                <span className="font-arabic text-muted/60 text-sm ml-2" dir="rtl">{s.ar}</span>
              </h3>
              <p className="text-[14px] text-muted leading-relaxed">{s.body}</p>
            </li>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}

// ----------------------------------------------------------------------------
// WHAT YOU GET
// ----------------------------------------------------------------------------
function WhatYouGet() {
  const items = [
    { icon: Music4, title: "Original vocals", body: "A real sung performance of your song — melody and voice, not a robotic read-out." },
    { icon: ScrollText, title: "Written lyrics", body: "Full Arabic lyrics you can preview and refine before anything is sung. Free to draft." },
    { icon: Disc3, title: "Album cover", body: "Cover art generated to match the mood of each song — ready to post." },
    { icon: Share2, title: "A song page", body: "A shareable page with a lyric reveal, plus the audio file to keep or send anywhere." },
    { icon: Mic2, title: "A voice you keep", body: "Save a voice so the same singer carries across every song you make." },
    { icon: Heart, title: "Pay only when you love it", body: "Drafting lyrics is always free. A credit is spent only when you approve the full song." },
  ];
  return (
    <Section eyebrow="WHAT YOU GET" title="Everything a song needs." ar="كل ما تحتاجه الأغنية">
      <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((it, i) => (
          <Reveal key={it.title} delay={(i % 3) * 0.06}>
            <div className="h-full rounded-2xl border border-white/10 bg-white/[0.02] p-6 hover:border-white/20 transition-colors">
              <div className="w-10 h-10 rounded-xl grid place-items-center mb-4 bg-gradient-to-br from-accent/15 via-rose/10 to-accent2/15 border border-white/10">
                <it.icon className="w-4.5 h-4.5 text-rose" />
              </div>
              <h3 className="text-[15px] font-semibold tracking-tight mb-1.5">{it.title}</h3>
              <p className="text-[13px] text-muted leading-relaxed">{it.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

// ----------------------------------------------------------------------------
// SHOWCASE — illustrative "theme → track" cards (gradient covers, not fake audio)
// ----------------------------------------------------------------------------
function Showcase() {
  const cards = [
    { title: "ليل بيروت", en: "Ballad", from: "from-indigo-500/40", to: "to-rose/40" },
    { title: "طريق العودة", en: "Folk", from: "from-amber-500/40", to: "to-accent2/40" },
    { title: "صيف الحب", en: "Pop", from: "from-rose/50", to: "to-orange-400/40" },
    { title: "همسة قمر", en: "Lo-fi", from: "from-accent2/50", to: "to-cyan-400/30" },
    { title: "زفة العريس", en: "Wedding", from: "from-accent/50", to: "to-rose/40" },
    { title: "وطن", en: "Anthem", from: "from-emerald-500/40", to: "to-accent/40" },
  ];
  return (
    <Section id="songs" eyebrow="A FEW THEMES → TRACKS" title="Any mood becomes a song." ar="كل إحساس يصير أغنية">
      <p className="text-[14px] text-muted max-w-xl mt-4">
        Pick a feeling and a style — a ballad, folk, pop, an anthem — and Faceless Lab writes and sings it in Arabic. A taste of what you can make:
      </p>
      <div className="mt-12 grid grid-cols-2 md:grid-cols-3 gap-4">
        {cards.map((c, i) => (
          <Reveal key={c.title} delay={(i % 3) * 0.06}>
            <div className="group relative aspect-square rounded-2xl overflow-hidden border border-white/10">
              <div className={`absolute inset-0 bg-gradient-to-br ${c.from} ${c.to}`} />
              <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/40 to-transparent" />
              {/* play glyph */}
              <div className="absolute top-3 right-3 w-9 h-9 rounded-full grid place-items-center bg-black/30 backdrop-blur border border-white/20 opacity-90 group-hover:scale-110 transition-transform">
                <div className="w-0 h-0 ml-0.5 border-y-[6px] border-y-transparent border-l-[10px] border-l-white" />
              </div>
              <div className="absolute inset-x-0 bottom-0 p-4">
                <div className="h-8 mb-2 opacity-80"><Waveform bars={28} /></div>
                <div className="flex items-end justify-between gap-2">
                  <span className="font-arabic text-lg leading-none" dir="rtl">{c.title}</span>
                  <span className="text-[10px] tracking-widest uppercase text-muted">{c.en}</span>
                </div>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
      <p className="text-[12px] text-muted/60 mt-6">Illustrative — your songs are yours to keep and share.</p>
    </Section>
  );
}

// ----------------------------------------------------------------------------
// WHY
// ----------------------------------------------------------------------------
function Why() {
  const points = [
    { title: "Arabic-first", body: "Written and sung in Arabic from your idea — not translated through another language on the way." },
    { title: "Free to try", body: "Draft as many sets of lyrics as you like for free. You only spend a credit when you approve the full song." },
    { title: "Your song is yours", body: "Keep the audio, the lyrics, and the cover. Post it anywhere, no strings attached." },
    { title: "Made for sharing", body: "Every song comes with a page and a lyric reveal built to look right on a phone." },
  ];
  return (
    <Section eyebrow="WHY FACELESS LAB" title="What we won't compromise on." ar="ما لا نتنازل عنه">
      <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 gap-4">
        {points.map((p, i) => (
          <Reveal key={p.title} delay={(i % 2) * 0.06}>
            <div className="flex gap-4 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <Check className="w-5 h-5 text-rose shrink-0 mt-0.5" />
              <div>
                <h3 className="text-[15px] font-semibold tracking-tight mb-1">{p.title}</h3>
                <p className="text-[13px] text-muted leading-relaxed">{p.body}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

// ----------------------------------------------------------------------------
// PRICING TEASER — links to /pricing for detail
// ----------------------------------------------------------------------------
function PricingTeaser() {
  const tiers = [
    { name: "Silver", price: 9, credits: 12, featured: false },
    { name: "Gold", price: 29, credits: 60, featured: true },
    { name: "Platinum", price: 79, credits: 200, featured: false },
  ];
  return (
    <Section id="pricing" eyebrow="PRICING" title="One credit makes a song." ar="رصيد واحد = أغنية">
      <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {tiers.map((t, i) => (
          <Reveal key={t.name} delay={i * 0.06}>
            <div className={`h-full rounded-2xl p-6 flex flex-col ${t.featured ? "border-2 border-transparent bg-surface [background:linear-gradient(theme(colors.surface),theme(colors.surface))_padding-box,linear-gradient(to_right,#E7B53C,#EC8FA9,#8B5CF6)_border-box] border-2" : "border border-white/10 bg-white/[0.02]"}`}>
              {t.featured && <div className="self-start text-[10px] font-bold tracking-[0.16em] mb-3 bg-gradient-to-r from-accent via-rose to-accent2 bg-clip-text text-transparent">MOST POPULAR</div>}
              <h3 className="text-lg font-semibold tracking-tight">{t.name}</h3>
              <div className="flex items-baseline gap-1 mt-2">
                <span className="font-display text-4xl">${t.price}</span>
                <span className="text-muted text-sm">/mo</span>
              </div>
              <div className="text-[13px] text-rose mt-1">{t.credits} credits / month</div>
            </div>
          </Reveal>
        ))}
      </div>
      <div className="mt-8">
        <a href="/pricing" className="inline-flex items-center gap-2 text-[14px] font-medium text-ink hover:text-rose transition-colors">
          See full plans <ArrowRight className="w-4 h-4" />
        </a>
      </div>
    </Section>
  );
}

// ----------------------------------------------------------------------------
// FINAL CTA
// ----------------------------------------------------------------------------
function FinalCTA() {
  return (
    <section className="relative overflow-hidden px-5 sm:px-8 py-28 sm:py-32">
      <div aria-hidden className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-1/2 -translate-y-1/2 h-[380px] w-[720px] max-w-[120vw] rounded-full blur-[120px] opacity-30"
           style={{ background: "radial-gradient(ellipse at center, rgba(236,143,169,0.5), rgba(139,92,246,0.3) 55%, transparent 72%)" }} />
      <div className="max-w-2xl mx-auto text-center">
        <div className="inline-flex mb-7"><SparkleLogo size={46} /></div>
        <h2 className="font-display font-medium tracking-[-0.02em] text-4xl sm:text-6xl leading-[1.03]">
          Your first song is <span className="italic bg-gradient-to-r from-accent via-rose to-accent2 bg-clip-text text-transparent">free.</span>
        </h2>
        <p className="text-muted max-w-md mx-auto mt-5">
          Write one line and hear the lyrics come back. Sing the full song whenever you're ready.
        </p>
        <a href={`${APP_URL}/`}
          className="mt-9 inline-flex items-center gap-2 text-base font-semibold px-7 py-3.5 rounded-full text-bg bg-gradient-to-r from-accent via-rose to-accent2 hover:brightness-110 transition shadow-xl shadow-rose/20">
          <Sparkles className="w-4 h-4" /> Start free <ArrowRight className="w-4 h-4" />
        </a>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------
// PRIMITIVES
// ----------------------------------------------------------------------------
function Section({ id, eyebrow, title, ar, children }: {
  id?: string; eyebrow: string; title: string; ar: string; children: React.ReactNode;
}) {
  return (
    <section id={id} className="relative py-24 px-5 sm:px-8 border-t border-white/[0.05]">
      <div className="max-w-5xl mx-auto">
        <Reveal>
          <div className="flex items-center gap-3 mb-4">
            <span className="w-8 h-px bg-gradient-to-r from-accent to-rose" />
            <span className="text-[10px] font-bold tracking-[0.22em] text-rose">{eyebrow}</span>
          </div>
          <h2 className="font-display font-medium tracking-[-0.02em] leading-tight text-3xl sm:text-5xl">
            {title}
            <span className="font-arabic text-muted/50 text-xl sm:text-2xl font-normal ml-3" dir="rtl">{ar}</span>
          </h2>
        </Reveal>
        {children}
      </div>
    </section>
  );
}

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
