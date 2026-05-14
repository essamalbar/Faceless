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
  Play,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";
import { LazyVideo } from "@/components/lazy-video";
import { useEffect, useState } from "react";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  "https://faceless-api-uplzdtffeq-uc.a.run.app";

// ----------------------------------------------------------------------------
// All atmospheric clips come from Mixkit's free-stock library (CC0,
// commercial use OK). IDs scraped from their horror / mystery / dark /
// alone / walking / silhouette / shadow / cinematic categories so the
// content matches the brand. URL pattern:
//   https://assets.mixkit.co/videos/<id>/<id>-720.mp4
// ----------------------------------------------------------------------------
const mp4 = (id: number) =>
  `https://assets.mixkit.co/videos/${id}/${id}-720.mp4`;

const HERO_VIDEO = mp4(30605); // night / horror — atmospheric hero loop

const THEMES = [
  { id: "folkloric",  en: "Folkloric",  ar: "فلكلوري", vid: 5565,  blurb: "Ancestral tales, jinn, old wells" },
  { id: "memory",     en: "Memory",     ar: "الذاكرة", vid: 46147, blurb: "Psychological, half-remembered" },
  { id: "wilderness", en: "Wilderness", ar: "البرية",  vid: 46138, blurb: "Forests, deserts, the unknown" },
  { id: "urban",      en: "Urban",      ar: "مدني",   vid: 30563, blurb: "City legends, late-night streets" },
  { id: "domestic",   en: "Domestic",   ar: "منزلي",  vid: 35889, blurb: "Home, family, the everyday turned" },
  { id: "travel",     en: "Travel",     ar: "سفر",    vid: 23410, blurb: "On the road, far from home" },
];

const SHOWREEL = [
  { vid: 46702, caption: "وحيدًا في الليل",    tag: "Memory · 90s" },
  { vid: 47442, caption: "البئر المهجور",      tag: "Folkloric · 2m" },
  { vid: 9582,  caption: "ضوء بعيد",            tag: "Wilderness · 75s" },
  { vid: 23818, caption: "صوت من الجدار",      tag: "Domestic · 60s" },
  { vid: 35426, caption: "ظل في الزقاق",       tag: "Urban · 90s" },
  { vid: 25896, caption: "الطريق الفارغ",      tag: "Travel · 2m" },
];

// ============================================================================
// PAGE
// ============================================================================
export default function Page() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-hidden">
      <Nav />
      <Hero />
      <Showreel />
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
          ? "backdrop-blur-xl bg-bg/85 border-b border-white/[0.06]"
          : ""
      }`}
    >
      <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center">
        <a href="#" className="flex items-center gap-2.5">
          <SparkleLogo size={28} />
          <span className="font-semibold text-[15px] tracking-tight">
            Faceless
          </span>
        </a>
        <nav className="hidden md:flex items-center gap-7 ml-12 text-[13px] text-muted">
          <a href="#templates" className="hover:text-ink transition-colors">Templates</a>
          <a href="#showreel" className="hover:text-ink transition-colors">Showreel</a>
          <a href="#features" className="hover:text-ink transition-colors">Features</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
        </nav>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <a href={`${APP_URL}/`} className="text-[13px] text-muted hover:text-ink px-3 py-2">
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

// ============================================================================
// HERO — full-bleed atmospheric video background, big bold typography
// ============================================================================
function Hero() {
  return (
    <section className="relative h-[100vh] min-h-[640px] overflow-hidden flex items-center">
      {/* Full-bleed looping video — the artlist-style hook */}
      <div className="absolute inset-0">
        <LazyVideo
          src={HERO_VIDEO}
          className="w-full h-full"
          rootMargin="0px"
          preload="auto"
        />
      </div>
      {/* Layered overlays for legibility */}
      <div className="absolute inset-0 bg-gradient-to-b from-bg/30 via-bg/60 to-bg" />
      <div className="absolute inset-0 bg-gradient-to-r from-bg/80 via-bg/30 to-transparent" />

      <div className="relative max-w-7xl mx-auto px-5 sm:px-8 w-full">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 mb-6 px-3 py-1 rounded-full border border-white/15 bg-black/40 backdrop-blur-sm text-[11px] tracking-wide"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          AI Arabic horror shorts
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
          className="text-[52px] sm:text-7xl lg:text-[100px] font-semibold tracking-[-0.045em] leading-[0.96] max-w-5xl mb-7"
        >
          Write one line.
          <br />
          <span className="bg-gradient-to-br from-accent via-amber-200 to-accent2 bg-clip-text text-transparent">
            Get a cinematic short.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg sm:text-xl text-ink/85 max-w-2xl mb-3 leading-relaxed"
        >
          Faceless writes the script, casts the characters, voices them in
          Arabic, and renders the video. You write the first sentence.
        </motion.p>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-base text-muted/80 max-w-xl mb-10 font-arabic"
          dir="rtl"
        >
          من جملة واحدة إلى فيلم قصير كامل بالعربية
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="flex flex-col sm:flex-row items-start sm:items-center gap-3"
        >
          <a
            href={`${APP_URL}/`}
            className="group bg-accent text-bg font-semibold text-base px-7 py-3.5 rounded-lg flex items-center gap-2 hover:bg-accent/90 transition-all hover:scale-[1.02] shadow-xl shadow-accent/20"
          >
            <Sparkles className="w-4 h-4" />
            Start creating free
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </a>
          <a
            href="#showreel"
            className="group flex items-center gap-3 text-ink hover:text-ink/80 font-medium px-2 py-3.5 transition-colors"
          >
            <span className="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 group-hover:bg-white/15 flex items-center justify-center transition-colors">
              <Play className="w-4 h-4 fill-current ml-0.5" />
            </span>
            Watch the showreel
          </a>
        </motion.div>
      </div>

      {/* Scroll cue */}
      <motion.div
        animate={{ y: [0, 6, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1.5 text-muted/60 text-[10px] tracking-[0.2em]"
      >
        SCROLL
        <div className="w-px h-6 bg-gradient-to-b from-muted/60 to-transparent" />
      </motion.div>
    </section>
  );
}

// ============================================================================
// SHOWREEL — Netflix-style horizontal scroll row of looping clips
// ============================================================================
function Showreel() {
  return (
    <section id="showreel" className="relative py-20 sm:py-24 border-t border-white/[0.05]">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 mb-8 sm:mb-10">
        <SectionEyebrow text="THE LIBRARY" />
        <SectionTitle en="Stories rendered." ar="قصص جاهزة" />
        <p className="mt-4 text-muted max-w-2xl">
          A glimpse of what visitors land on. Every clip rendered from a
          one-line premise, characters and voices locked across beats.
        </p>
      </div>
      {/* Horizontal scroll row, edge-to-edge for that artlist feel */}
      <div className="relative">
        <div className="flex gap-3 sm:gap-4 overflow-x-auto px-5 sm:px-8 pb-6 snap-x snap-mandatory scrollbar-hide">
          {SHOWREEL.map((s, i) => (
            <ShowreelTile key={i} item={s} index={i} />
          ))}
          <div className="flex-shrink-0 w-1" />
        </div>
        <style jsx>{`
          .scrollbar-hide::-webkit-scrollbar { display: none; }
          .scrollbar-hide { scrollbar-width: none; -ms-overflow-style: none; }
        `}</style>
      </div>
    </section>
  );
}

function ShowreelTile({
  item,
  index,
}: {
  item: (typeof SHOWREEL)[number];
  index: number;
}) {
  return (
    <motion.a
      href={`${APP_URL}/`}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.5, delay: (index % 3) * 0.06 }}
      className="group flex-shrink-0 snap-start relative w-[260px] sm:w-[300px] aspect-[9/16] rounded-2xl overflow-hidden border border-white/10 hover:border-white/30 transition-all"
    >
      <LazyVideo
        src={mp4(item.vid)}
        className="absolute inset-0 w-full h-full"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent" />
      <div className="absolute inset-0 p-4 flex flex-col justify-end">
        <div className="text-[10px] font-medium text-white/65 tracking-[0.18em] uppercase mb-1">
          {item.tag}
        </div>
        <div className="text-base sm:text-lg font-semibold text-white font-arabic tracking-tight" dir="rtl">
          {item.caption}
        </div>
      </div>
    </motion.a>
  );
}

// ============================================================================
// FEATURES
// ============================================================================
function Features() {
  const items = [
    { icon: Wand2,     title: "AI script writer",   body: "One sentence becomes a full Arabic script. Dialogue, characters, shot directions." },
    { icon: Film,      title: "Cinematic video",    body: "Each beat becomes a clip. Stitched with music and captions. 9:16, ready to share." },
    { icon: Languages, title: "Authentic Arabic",   body: "MSA or dialect, your choice. Real Arabic voice acting — not a translation." },
    { icon: FileText,  title: "Free script PDF",    body: "Export the director's script even without a subscription. Cover, cast, beats." },
  ];
  return (
    <section id="features" className="relative py-24 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="WHAT YOU GET" />
        <SectionTitle en="An entire crew. In your pocket." ar="طاقم إنتاج كامل في جيبك" />
        <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {items.map((it, i) => (
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="bg-white/[0.02] border border-white/10 rounded-xl p-6 hover:bg-white/[0.04] hover:border-white/20 transition-colors"
            >
              <div className="w-9 h-9 rounded-lg border border-white/10 flex items-center justify-center mb-5">
                <it.icon className="w-4 h-4 text-accent" />
              </div>
              <h3 className="text-[15px] font-semibold mb-1.5 tracking-tight">
                {it.title}
              </h3>
              <p className="text-[13px] text-muted leading-relaxed">
                {it.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// TEMPLATES — every card a looping video preview
// ============================================================================
function Templates() {
  return (
    <section id="templates" className="relative py-24 px-5 sm:px-8 border-t border-white/[0.05]">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="TEMPLATES" />
        <SectionTitle en="Six places to start." ar="ست نقاط بداية" />
        <p className="mt-4 text-muted max-w-2xl">
          Pick a setting. The AI writes a story around your one-line premise.
        </p>
        <div className="mt-14 grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {THEMES.map((t, i) => (
            <motion.a
              key={t.id}
              href={`${APP_URL}/?theme=${t.id}`}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.04 }}
              className="group relative aspect-[4/5] rounded-2xl overflow-hidden border border-white/10 hover:border-white/30 transition-colors"
            >
              <LazyVideo
                src={mp4(t.vid)}
                className="absolute inset-0 w-full h-full"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent" />
              <div className="absolute inset-0 p-5 flex flex-col justify-end">
                <div className="text-[10px] font-medium text-white/65 tracking-[0.18em] uppercase mb-1">
                  {t.en}
                </div>
                <div
                  className="text-xl sm:text-2xl font-semibold text-white tracking-tight font-arabic mb-1"
                  dir="rtl"
                >
                  {t.ar}
                </div>
                <p className="text-[11px] text-white/65 leading-snug line-clamp-2">
                  {t.blurb}
                </p>
              </div>
              <div className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/50 backdrop-blur-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <ArrowRight className="w-3.5 h-3.5 text-white" />
              </div>
            </motion.a>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PRICING
// ============================================================================
function Pricing() {
  const tiers = [
    { name: "Starter", price: "$9",  credits: 12,  blurb: "For trying ideas",  perks: ["12 video clips / month", "All templates", "Free script PDF"] },
    { name: "Creator", price: "$29", credits: 60,  blurb: "For weekly drops",  recommended: true, perks: ["60 video clips / month", "Priority rendering", "All templates", "Free script PDF"] },
    { name: "Pro",     price: "$79", credits: 200, blurb: "For daily output",  perks: ["200 video clips / month", "Priority rendering", "All templates", "Free script PDF"] },
  ];
  return (
    <section id="pricing" className="relative py-24 px-5 sm:px-8 border-t border-white/[0.05]">
      <div className="max-w-5xl mx-auto">
        <SectionEyebrow text="PRICING" />
        <SectionTitle en="Subscribe once. Render every month." ar="اشترك مرة. ارند كل شهر" />
        <p className="mt-4 text-muted max-w-2xl">
          1 credit = 1 video clip. Pause or change tier any time.
        </p>
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
                  ? "bg-accent/[0.08] border-accent/40"
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
                className={`block text-center font-semibold text-sm py-2.5 rounded-md transition-colors ${
                  t.recommended
                    ? "bg-accent text-bg hover:bg-accent/90"
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
    <section className="relative py-28 sm:py-32 px-5 sm:px-8 overflow-hidden border-t border-white/[0.05]">
      <div className="absolute inset-0 opacity-30">
        <LazyVideo src={mp4(8537)} className="w-full h-full" rootMargin="0px" />
      </div>
      <div className="absolute inset-0 bg-gradient-to-b from-bg via-bg/60 to-bg" />
      <div className="relative max-w-3xl mx-auto text-center">
        <div className="inline-flex justify-center mb-7">
          <SparkleLogo size={56} />
        </div>
        <h2 className="text-4xl sm:text-6xl font-semibold tracking-[-0.035em] mb-5">
          Your first story is free.
        </h2>
        <p className="text-base sm:text-lg text-muted max-w-md mx-auto mb-9">
          Write one sentence. We do the rest. Render whenever you're ready.
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

// ============================================================================
// FOOTER
// ============================================================================
function Footer() {
  return (
    <footer className="border-t border-white/[0.06] py-10 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center gap-5">
        <div className="flex items-center gap-2.5">
          <SparkleLogo size={22} />
          <span className="text-[13px] text-muted">
            Faceless · made for Arabic storytellers
          </span>
        </div>
        <div className="sm:ml-auto flex items-center gap-6 text-[13px] text-muted">
          <a href="#templates" className="hover:text-ink transition-colors">Templates</a>
          <a href="#showreel" className="hover:text-ink transition-colors">Showreel</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href={`${APP_URL}/`} className="hover:text-ink transition-colors">Sign in</a>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// PRIMITIVES
// ============================================================================
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
    <motion.h2
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5 }}
      className="text-3xl sm:text-5xl lg:text-6xl font-semibold tracking-[-0.03em] leading-tight"
    >
      {en}
      <span
        className="ml-3 text-muted/60 text-xl sm:text-2xl font-normal font-arabic"
        dir="rtl"
      >
        {ar}
      </span>
    </motion.h2>
  );
}
