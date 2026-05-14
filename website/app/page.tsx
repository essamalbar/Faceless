"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  Sparkles,
  Wand2,
  Film,
  Languages,
  FileText,
  ArrowRight,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";

// The same URL run-app.sh prints + the Cloud Run URL the Flutter app
// is hosted on. Change in ONE place and every CTA across the site
// updates.
const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "https://faceless-api-uplzdtffeq-uc.a.run.app";

// =============================================================================
// THEME TEMPLATES — same 8 themes the home screen offers, used here as
// "templates" the visitor can imagine themselves picking on day one.
// =============================================================================
const THEMES = [
  {
    id: "folkloric",
    en: "Folkloric",
    ar: "فلكلوري",
    desc: "Ancestral tales, jinn, old wells",
    grad: ["#B07F1F", "#E7B53C"],
  },
  {
    id: "urban",
    en: "Urban",
    ar: "مدني",
    desc: "City legends, late-night streets",
    grad: ["#3B82F6", "#1E40AF"],
  },
  {
    id: "wilderness",
    en: "Wilderness",
    ar: "البرية",
    desc: "Forests, deserts, the unknown",
    grad: ["#059669", "#064E3B"],
  },
  {
    id: "memory",
    en: "Memory",
    ar: "الذاكرة",
    desc: "Psychological, half-remembered",
    grad: ["#8B5CF6", "#5B21B6"],
  },
  {
    id: "domestic",
    en: "Domestic",
    ar: "منزلي",
    desc: "Home, family, the everyday turned",
    grad: ["#EA580C", "#9A3412"],
  },
  {
    id: "travel",
    en: "Travel",
    ar: "سفر",
    desc: "On the road, far from home",
    grad: ["#0D9488", "#134E4A"],
  },
  {
    id: "tech",
    en: "Tech",
    ar: "تقني",
    desc: "Screens, signals, machines",
    grad: ["#06B6D4", "#155E75"],
  },
  {
    id: "workplace",
    en: "Workplace",
    ar: "العمل",
    desc: "Offices, shops, after-hours",
    grad: ["#64748B", "#334155"],
  },
];

// =============================================================================
// PAGE
// =============================================================================
export default function Page() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-hidden">
      <TopNav />
      <Hero />
      <Features />
      <Templates />
      <ThreeDShowcase />
      <Pricing />
      <FinalCTA />
      <Footer />
    </main>
  );
}

// =============================================================================
// TOP NAV
// =============================================================================
function TopNav() {
  return (
    <header className="fixed top-0 left-0 right-0 z-40 backdrop-blur-md bg-bg/70 border-b border-white/5">
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-3 flex items-center">
        <a href="#" className="flex items-center gap-2.5">
          <SparkleLogo size={32} />
          <span className="font-bold text-lg tracking-tight">Faceless</span>
        </a>
        <nav className="hidden md:flex items-center gap-8 ml-12 text-sm text-muted">
          <a href="#features" className="hover:text-ink transition-colors">Features</a>
          <a href="#templates" className="hover:text-ink transition-colors">Templates</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <a
            href={`${APP_URL}/`}
            className="text-sm text-muted hover:text-ink px-3 py-2"
          >
            Sign in
          </a>
          <a
            href={`${APP_URL}/`}
            className="bg-accent text-bg font-semibold text-sm px-4 py-2 rounded-lg hover:bg-accent/90 transition-colors"
          >
            Start free
          </a>
        </div>
      </div>
    </header>
  );
}

// =============================================================================
// HERO
// =============================================================================
function Hero() {
  return (
    <section className="relative pt-32 sm:pt-40 pb-20 sm:pb-32 px-5 sm:px-8 overflow-hidden">
      {/* Ambient gold glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 50% 30%, rgba(231,181,60,0.18), transparent 60%)",
        }}
      />
      {/* Drifting orbs in the bg for depth */}
      <FloatingOrb className="top-1/3 left-1/4 w-80 h-80" hue="#E7B53C" delay={0} />
      <FloatingOrb className="top-1/2 right-1/4 w-72 h-72" hue="#8B5CF6" delay={2} />

      <div className="relative max-w-4xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 mb-6 px-3 py-1 rounded-full border border-accent/30 bg-accent/10"
        >
          <Sparkles className="w-3.5 h-3.5 text-accent" />
          <span className="text-xs font-semibold text-accent tracking-wide">
            AI-POWERED ARABIC STORYTELLING
          </span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mb-6 flex justify-center"
        >
          <div className="relative">
            <div
              className="absolute inset-0 blur-3xl opacity-50"
              style={{ background: "#E7B53C" }}
            />
            <div className="relative">
              <SparkleLogo size={96} />
            </div>
          </div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-5xl sm:text-7xl font-extrabold tracking-tight mb-5"
        >
          Faceless
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-xl sm:text-2xl text-ink/90 mb-2 font-light"
        >
          Turn a one-line premise into a cinematic Arabic short.
        </motion.p>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="text-lg text-muted mb-10 font-arabic"
          dir="rtl"
        >
          اصنع قصصك القصيرة بالذكاء الاصطناعي
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex flex-col sm:flex-row gap-3 justify-center items-center"
        >
          <a
            href={`${APP_URL}/`}
            className="group bg-accent text-bg font-bold px-7 py-3.5 rounded-xl text-base flex items-center gap-2 hover:bg-accent/90 transition-all hover:scale-105"
          >
            <Sparkles className="w-4 h-4" />
            Start creating free
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="#features"
            className="text-muted hover:text-ink font-medium px-5 py-3.5 transition-colors"
          >
            How it works ↓
          </a>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.7 }}
          className="text-xs text-muted/70 mt-6 tracking-wide"
        >
          Free to write your script · Subscribe to render the video
        </motion.p>
      </div>
    </section>
  );
}

function FloatingOrb({
  className,
  hue,
  delay,
}: {
  className: string;
  hue: string;
  delay: number;
}) {
  return (
    <motion.div
      className={`absolute rounded-full blur-3xl opacity-30 pointer-events-none ${className}`}
      style={{ background: hue }}
      animate={{ y: [0, -20, 0], x: [0, 10, 0] }}
      transition={{ duration: 8, delay, repeat: Infinity, ease: "easeInOut" }}
    />
  );
}

// =============================================================================
// FEATURES
// =============================================================================
function Features() {
  const items = [
    {
      icon: Wand2,
      title: "AI script writer",
      body: "One sentence in. A full Arabic script out, with dialogue, character names, shot descriptions — ready to render.",
    },
    {
      icon: Film,
      title: "Cinematic video",
      body: "Each beat becomes a clip. Characters stay consistent. Lip-synced dialogue, music, and captions, stitched into a final mp4.",
    },
    {
      icon: Languages,
      title: "Authentic Arabic",
      body: "MSA or dialect — your call. Voice acting in Arabic, not a Western voice trying to sound Arab. Made for Arab audiences.",
    },
    {
      icon: FileText,
      title: "Free PDF export",
      body: "Even on the free tier, take the full director's-script PDF home: cover page, cast list, every beat with VISUAL + DIALOGUE blocks.",
    },
  ];

  return (
    <section id="features" className="relative py-20 px-5 sm:px-8">
      <div className="max-w-6xl mx-auto">
        <SectionHeading en="What you get" ar="ماذا تحصل" />
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {items.map((it, i) => (
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="bg-surface border border-white/10 rounded-2xl p-6 hover:border-accent/40 transition-colors"
            >
              <div className="w-11 h-11 rounded-full bg-accent/15 border border-accent/30 flex items-center justify-center mb-4">
                <it.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="font-bold text-lg mb-2">{it.title}</h3>
              <p className="text-sm text-muted leading-relaxed">{it.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// TEMPLATES — 8 theme cards. Tapping any one deep-links into the app's
// new-run flow pre-filled with that theme.
// =============================================================================
function Templates() {
  return (
    <section id="templates" className="relative py-20 px-5 sm:px-8 bg-surface/30">
      <div className="max-w-6xl mx-auto">
        <SectionHeading
          en="Templates"
          ar="قوالب"
          sub="Pick a vibe to start from. The AI shapes the story around it."
        />
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {THEMES.map((t, i) => (
            <motion.a
              key={t.id}
              href={`${APP_URL}/?theme=${t.id}`}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.05 }}
              className="group relative aspect-[4/5] rounded-2xl overflow-hidden border border-white/10 hover:border-white/30 transition-all hover:scale-[1.02]"
              style={{
                background: `linear-gradient(135deg, ${t.grad[0]}, ${t.grad[1]})`,
              }}
            >
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
              <div className="absolute inset-0 p-5 flex flex-col justify-end">
                <div className="text-xs font-semibold text-white/70 tracking-wider mb-1 uppercase">
                  {t.en}
                </div>
                <div
                  className="text-2xl font-bold text-white mb-2 font-arabic"
                  dir="rtl"
                >
                  {t.ar}
                </div>
                <p className="text-xs text-white/80 leading-relaxed">
                  {t.desc}
                </p>
              </div>
              <div className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <ArrowRight className="w-4 h-4 text-white" />
              </div>
            </motion.a>
          ))}
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// 3D SCROLL SHOWCASE — parallax tilted cards that animate in with depth
// as you scroll. The bottom-of-page "wow" moment.
// =============================================================================
function ThreeDShowcase() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });

  // Each card gets its own scroll-driven transforms — different angles
  // and offsets so the trio reads as a 3D fan as the user scrolls past.
  const card1Y = useTransform(scrollYProgress, [0, 1], [120, -120]);
  const card1Rot = useTransform(scrollYProgress, [0, 1], [-20, 20]);
  const card2Y = useTransform(scrollYProgress, [0, 1], [60, -60]);
  const card3Y = useTransform(scrollYProgress, [0, 1], [120, -120]);
  const card3Rot = useTransform(scrollYProgress, [0, 1], [20, -20]);

  return (
    <section ref={ref} className="relative py-32 px-5 sm:px-8 overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% 50%, rgba(139,92,246,0.18), transparent 70%)",
        }}
      />
      <div className="relative max-w-6xl mx-auto">
        <SectionHeading
          en="See it move"
          ar="شاهدها تتحرك"
          sub="Every beat is a cinematic clip. Stitched, scored, captioned, ready to share."
        />

        {/* Card grid — perspective-tilted with scroll-driven parallax */}
        <div
          className="mt-16 relative h-[480px] flex items-center justify-center"
          style={{ perspective: "1500px" }}
        >
          <motion.div
            style={{
              y: card1Y,
              rotateY: card1Rot,
              rotateZ: -8,
              x: -150,
              transformStyle: "preserve-3d",
            }}
            className="absolute w-56 aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border border-white/20"
          >
            <ThemePoster theme={THEMES[0]} />
          </motion.div>

          <motion.div
            style={{ y: card2Y, transformStyle: "preserve-3d" }}
            className="absolute w-64 aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border-2 border-accent/40 z-10"
          >
            <ThemePoster theme={THEMES[3]} />
          </motion.div>

          <motion.div
            style={{
              y: card3Y,
              rotateY: card3Rot,
              rotateZ: 8,
              x: 150,
              transformStyle: "preserve-3d",
            }}
            className="absolute w-56 aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border border-white/20"
          >
            <ThemePoster theme={THEMES[6]} />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function ThemePoster({ theme }: { theme: (typeof THEMES)[number] }) {
  return (
    <div
      className="w-full h-full relative"
      style={{
        background: `linear-gradient(135deg, ${theme.grad[0]}, ${theme.grad[1]})`,
      }}
    >
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
      <div className="absolute inset-0 p-5 flex flex-col justify-end">
        <div
          className="text-xl font-bold text-white mb-1 font-arabic"
          dir="rtl"
        >
          {theme.ar}
        </div>
        <div className="text-xs text-white/70 uppercase tracking-wider">
          {theme.en}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// PRICING
// =============================================================================
function Pricing() {
  const tiers = [
    { name: "Starter", price: "$9", credits: 12, blurb: "For trying ideas" },
    { name: "Creator", price: "$29", credits: 60, blurb: "For weekly drops", recommended: true },
    { name: "Pro", price: "$79", credits: 200, blurb: "For daily output" },
  ];
  return (
    <section id="pricing" className="relative py-20 px-5 sm:px-8">
      <div className="max-w-5xl mx-auto">
        <SectionHeading
          en="Pricing"
          ar="الأسعار"
          sub="1 credit = 1 video clip. Subscribe once, render every month."
        />
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-5">
          {tiers.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className={`rounded-2xl p-7 border ${
                t.recommended
                  ? "bg-accent/10 border-accent/50 scale-[1.02]"
                  : "bg-surface border-white/10"
              }`}
            >
              {t.recommended ? (
                <div className="inline-block text-[10px] font-bold tracking-wider px-2 py-1 rounded bg-accent/25 text-accent mb-3">
                  RECOMMENDED
                </div>
              ) : (
                <div className="h-[22px] mb-3" />
              )}
              <h3 className="text-xl font-bold mb-1">{t.name}</h3>
              <div className="flex items-baseline gap-1 mb-2">
                <span className="text-4xl font-extrabold text-accent">{t.price}</span>
                <span className="text-muted">/ month</span>
              </div>
              <div className="font-semibold text-sm mb-1">
                {t.credits} credits / month
              </div>
              <div className="text-xs text-muted mb-5">{t.blurb}</div>
              <a
                href={`${APP_URL}/`}
                className={`block text-center font-bold py-2.5 rounded-lg transition-colors ${
                  t.recommended
                    ? "bg-accent text-bg hover:bg-accent/90"
                    : "bg-white/5 text-ink hover:bg-white/10"
                }`}
              >
                Get {t.name}
              </a>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// FINAL CTA
// =============================================================================
function FinalCTA() {
  return (
    <section className="relative py-20 px-5 sm:px-8 overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 50% 50%, rgba(231,181,60,0.18), transparent 60%)",
        }}
      />
      <div className="relative max-w-3xl mx-auto text-center">
        <div className="inline-flex justify-center mb-6">
          <SparkleLogo size={64} />
        </div>
        <h2 className="text-4xl sm:text-5xl font-extrabold mb-4 tracking-tight">
          Your first story is free.
        </h2>
        <p className="text-lg text-muted mb-8">
          Write a one-sentence premise. The AI does the rest. No card required
          to start.
        </p>
        <a
          href={`${APP_URL}/`}
          className="inline-flex items-center gap-2 bg-accent text-bg font-bold px-8 py-4 rounded-xl text-base hover:bg-accent/90 transition-all hover:scale-105"
        >
          <Sparkles className="w-4 h-4" />
          Start creating
          <ArrowRight className="w-4 h-4" />
        </a>
      </div>
    </section>
  );
}

// =============================================================================
// FOOTER
// =============================================================================
function Footer() {
  return (
    <footer className="border-t border-white/5 py-10 px-5 sm:px-8">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center gap-4">
        <div className="flex items-center gap-2.5">
          <SparkleLogo size={24} />
          <span className="text-sm text-muted">Faceless · made for Arabic storytellers</span>
        </div>
        <div className="sm:ml-auto flex items-center gap-6 text-sm text-muted">
          <a href="#features" className="hover:text-ink transition-colors">Features</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href={`${APP_URL}/`} className="hover:text-ink transition-colors">Sign in</a>
        </div>
      </div>
    </footer>
  );
}

// =============================================================================
// SHARED
// =============================================================================
function SectionHeading({
  en,
  ar,
  sub,
}: {
  en: string;
  ar: string;
  sub?: string;
}) {
  return (
    <div>
      <div className="w-10 h-1 bg-accent rounded mb-4" />
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
          {en}
        </h2>
        <span className="text-xl text-muted/80 font-arabic" dir="rtl">
          {ar}
        </span>
      </div>
      {sub && <p className="mt-3 text-muted max-w-2xl">{sub}</p>}
    </div>
  );
}
