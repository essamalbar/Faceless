"use client";

import { motion } from "framer-motion";
import {
  Sparkles,
  Wand2,
  Film,
  Languages,
  FileText,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";
import { useEffect, useState } from "react";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  "https://faceless-api-uplzdtffeq-uc.a.run.app";

// ----------------------------------------------------------------------------
// Six theme templates — dropped two (tech, workplace) the user disliked.
// Photos chosen for atmosphere: silhouettes, fog, mountains. No tech cables.
// ----------------------------------------------------------------------------
const THEMES = [
  { id: "folkloric",  en: "Folkloric",  ar: "فلكلوري", photo: "1500964757637-c85e8a162699" },
  { id: "memory",     en: "Memory",     ar: "الذاكرة", photo: "1517423440428-a5a00ad493e8" },
  { id: "wilderness", en: "Wilderness", ar: "البرية",  photo: "1448375240586-882707db888b" },
  { id: "urban",      en: "Urban",      ar: "مدني",   photo: "1514924013411-cbf25faa35bb" },
  { id: "domestic",   en: "Domestic",   ar: "منزلي",  photo: "1505691938895-1758d7feb511" },
  { id: "travel",     en: "Travel",     ar: "سفر",    photo: "1502691876148-a84978e59af8" },
];

const photoUrl = (id: string, w = 900) =>
  `https://images.unsplash.com/photo-${id}?w=${w}&q=80&auto=format&fit=crop`;

// ============================================================================
// PAGE
// ============================================================================
export default function Page() {
  return (
    <main className="min-h-screen bg-bg text-ink">
      <Nav />
      <Hero />
      <Features />
      <Templates />
      <Pricing />
      <FinalCTA />
      <Footer />
    </main>
  );
}

// ============================================================================
// NAV
// ============================================================================
function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-colors duration-200 ${
        scrolled
          ? "backdrop-blur-md bg-bg/80 border-b border-white/[0.06]"
          : ""
      }`}
    >
      <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center">
        <a href="#" className="flex items-center gap-2.5">
          <SparkleLogo size={28} />
          <span className="font-semibold text-[15px] tracking-tight">
            Faceless
          </span>
        </a>
        <nav className="hidden md:flex items-center gap-7 ml-12 text-[13px] text-muted">
          <a href="#features" className="hover:text-ink transition-colors">
            Features
          </a>
          <a href="#templates" className="hover:text-ink transition-colors">
            Templates
          </a>
          <a href="#pricing" className="hover:text-ink transition-colors">
            Pricing
          </a>
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
            className="bg-ink text-bg font-medium text-[13px] px-4 py-2 rounded-md hover:bg-ink/90 transition-colors"
          >
            Get started
          </a>
        </div>
      </div>
    </header>
  );
}

// ============================================================================
// HERO — no background photo, no particles. Bold type, generous whitespace,
// one accent. Premium-SaaS feel.
// ============================================================================
function Hero() {
  return (
    <section className="relative pt-44 sm:pt-52 pb-28 sm:pb-36 px-5 sm:px-8">
      {/* Single subtle radial accent — quiet, not a fireworks show */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 50% 35% at 50% 0%, rgba(231,181,60,0.08), transparent 60%)",
        }}
      />
      <div className="relative max-w-4xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 mb-8 px-3 py-1 rounded-full border border-white/10 bg-white/[0.03] text-[11px] text-muted tracking-wide"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          New · AI Arabic horror shorts
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="text-[44px] sm:text-7xl lg:text-[88px] font-semibold tracking-[-0.035em] leading-[1.02] mb-7"
        >
          Write one line.
          <br />
          <span className="text-muted">Get a cinematic short.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="text-base sm:text-lg text-muted/90 max-w-xl mx-auto leading-relaxed mb-10"
        >
          Faceless writes the script, casts the characters, voices them in
          Arabic, and renders the video. You write the first sentence.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-2.5"
        >
          <a
            href={`${APP_URL}/`}
            className="group bg-ink text-bg font-medium text-sm px-5 py-2.5 rounded-md flex items-center gap-1.5 hover:bg-ink/90 transition-colors"
          >
            Start free
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </a>
          <a
            href="#templates"
            className="text-sm text-muted hover:text-ink font-medium px-5 py-2.5 transition-colors"
          >
            See templates →
          </a>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-xs text-muted/60 mt-8"
        >
          Free to write. Subscribe to render. No card required.
        </motion.p>
      </div>
    </section>
  );
}

// ============================================================================
// FEATURES — 4 clean cards
// ============================================================================
function Features() {
  const items = [
    {
      icon: Wand2,
      title: "AI script writer",
      body: "One sentence becomes a full Arabic script. Dialogue, characters, shot directions. Ready to render.",
    },
    {
      icon: Film,
      title: "Cinematic video",
      body: "Each beat becomes a clip. Stitched with music and captions. Output is mp4, 9:16, ready to share.",
    },
    {
      icon: Languages,
      title: "Authentic Arabic",
      body: "MSA or dialect, your choice. Real Arabic voice acting, not a translation.",
    },
    {
      icon: FileText,
      title: "Free script PDF",
      body: "Export the director's script even without a subscription. Cover, cast, beat by beat.",
    },
  ];

  return (
    <section id="features" className="relative py-24 px-5 sm:px-8">
      <div className="max-w-6xl mx-auto">
        <SectionHeader
          en="Everything you need to ship a story."
          ar="كل ما تحتاجه لإطلاق قصة"
        />
        <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {items.map((it, i) => (
            <Card key={it.title} delay={i * 0.06}>
              <div className="w-9 h-9 rounded-lg border border-white/10 flex items-center justify-center mb-5">
                <it.icon className="w-4 h-4 text-accent" />
              </div>
              <h3 className="text-[15px] font-semibold mb-1.5 tracking-tight">
                {it.title}
              </h3>
              <p className="text-[13px] text-muted leading-relaxed">
                {it.body}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// TEMPLATES — six clean photo cards
// ============================================================================
function Templates() {
  return (
    <section id="templates" className="relative py-24 px-5 sm:px-8">
      <div className="max-w-6xl mx-auto">
        <SectionHeader
          en="Six places to start."
          ar="ست نقاط بداية"
          sub="Pick a setting. The AI writes a story around it."
        />
        <div className="mt-14 grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {THEMES.map((t, i) => (
            <motion.a
              key={t.id}
              href={`${APP_URL}/?theme=${t.id}`}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.04 }}
              className="group relative aspect-[4/5] rounded-xl overflow-hidden border border-white/10 hover:border-white/25 transition-colors"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photoUrl(t.photo, 600)}
                alt={t.en}
                loading="lazy"
                className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.04]"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
              <div className="absolute inset-0 p-5 flex flex-col justify-end">
                <div className="text-[10px] font-medium text-white/65 tracking-[0.18em] mb-1 uppercase">
                  {t.en}
                </div>
                <div
                  className="text-xl sm:text-2xl font-semibold text-white tracking-tight font-arabic"
                  dir="rtl"
                >
                  {t.ar}
                </div>
              </div>
            </motion.a>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PRICING — three tiers, clean
// ============================================================================
function Pricing() {
  const tiers = [
    { name: "Starter", price: "$9", credits: 12, blurb: "For trying ideas", perks: ["12 video clips / month", "All templates", "Free script PDF"] },
    { name: "Creator", price: "$29", credits: 60, blurb: "For weekly drops", recommended: true, perks: ["60 video clips / month", "Priority rendering", "All templates", "Free script PDF"] },
    { name: "Pro", price: "$79", credits: 200, blurb: "For daily output", perks: ["200 video clips / month", "Priority rendering", "All templates", "Free script PDF"] },
  ];
  return (
    <section id="pricing" className="relative py-24 px-5 sm:px-8">
      <div className="max-w-5xl mx-auto">
        <SectionHeader
          en="Subscribe once. Render every month."
          ar="اشترك مرة. ارند كل شهر"
          sub="1 credit = 1 video clip. Pause or change tier any time."
        />
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-3">
          {tiers.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className={`relative rounded-xl p-7 border ${
                t.recommended
                  ? "bg-white/[0.04] border-white/25"
                  : "bg-white/[0.02] border-white/10"
              }`}
            >
              {t.recommended && (
                <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full bg-accent text-bg text-[10px] font-semibold tracking-wide">
                  RECOMMENDED
                </div>
              )}
              <h3 className="text-base font-semibold mb-1">{t.name}</h3>
              <div className="text-[13px] text-muted mb-6">{t.blurb}</div>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="text-4xl font-semibold tracking-tight">{t.price}</span>
                <span className="text-muted text-sm">/ mo</span>
              </div>
              <ul className="space-y-2 mb-7">
                {t.perks.map((p) => (
                  <li key={p} className="flex items-start gap-2 text-[13px] text-ink/90">
                    <CheckCircle2 className="w-3.5 h-3.5 text-accent flex-shrink-0 mt-0.5" />
                    {p}
                  </li>
                ))}
              </ul>
              <a
                href={`${APP_URL}/`}
                className={`block text-center font-medium text-sm py-2.5 rounded-md transition-colors ${
                  t.recommended
                    ? "bg-ink text-bg hover:bg-ink/90"
                    : "bg-white/5 text-ink hover:bg-white/10 border border-white/10"
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

// ============================================================================
// FINAL CTA
// ============================================================================
function FinalCTA() {
  return (
    <section className="relative py-32 px-5 sm:px-8 border-t border-white/[0.06]">
      <div className="max-w-3xl mx-auto text-center">
        <div className="inline-flex justify-center mb-7">
          <SparkleLogo size={44} />
        </div>
        <h2 className="text-3xl sm:text-5xl font-semibold tracking-[-0.03em] mb-5">
          Your first story is free.
        </h2>
        <p className="text-[15px] text-muted max-w-md mx-auto mb-9">
          Write one sentence. We do the rest. Render whenever you're ready.
        </p>
        <a
          href={`${APP_URL}/`}
          className="inline-flex items-center gap-1.5 bg-ink text-bg font-medium text-sm px-6 py-2.5 rounded-md hover:bg-ink/90 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" />
          Start free
        </a>
      </div>
    </section>
  );
}

// ============================================================================
// FOOTER
// ============================================================================
function Footer() {
  return (
    <footer className="border-t border-white/[0.06] py-10 px-5 sm:px-8">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center gap-5">
        <div className="flex items-center gap-2.5">
          <SparkleLogo size={22} />
          <span className="text-[13px] text-muted">
            Faceless · made for Arabic storytellers
          </span>
        </div>
        <div className="sm:ml-auto flex items-center gap-6 text-[13px] text-muted">
          <a href="#features" className="hover:text-ink transition-colors">
            Features
          </a>
          <a href="#templates" className="hover:text-ink transition-colors">
            Templates
          </a>
          <a href="#pricing" className="hover:text-ink transition-colors">
            Pricing
          </a>
          <a href={`${APP_URL}/`} className="hover:text-ink transition-colors">
            Sign in
          </a>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// PRIMITIVES
// ============================================================================
function SectionHeader({
  en,
  ar,
  sub,
}: {
  en: string;
  ar: string;
  sub?: string;
}) {
  return (
    <div className="max-w-3xl">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.5 }}
        className="text-3xl sm:text-5xl font-semibold tracking-[-0.03em] leading-tight"
      >
        {en}
        <span
          className="ml-3 text-muted/60 text-xl sm:text-2xl font-normal font-arabic"
          dir="rtl"
        >
          {ar}
        </span>
      </motion.h2>
      {sub && (
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-[15px] text-muted mt-3 max-w-2xl"
        >
          {sub}
        </motion.p>
      )}
    </div>
  );
}

function Card({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay }}
      className="bg-white/[0.02] border border-white/10 rounded-xl p-6 hover:bg-white/[0.04] hover:border-white/20 transition-colors"
    >
      {children}
    </motion.div>
  );
}
