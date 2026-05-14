"use client";

import { useEffect, useRef, useState } from "react";
import {
  motion,
  useInView,
  useScroll,
  useTransform,
  useMotionValue,
  useSpring,
} from "framer-motion";
import {
  Sparkles,
  Wand2,
  Film,
  Languages,
  FileText,
  ArrowRight,
  Play,
  Zap,
  CheckCircle2,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";
import { ParticleField } from "@/components/particle-field";
import { TiltCard } from "@/components/tilt-card";
import { ScrambleText } from "@/components/scramble-text";
import { GenerationPipeline } from "@/components/generation-pipeline";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  "https://faceless-api-uplzdtffeq-uc.a.run.app";

// ----------------------------------------------------------------------------
// IMAGE CDN — all photos come from Unsplash (CC0 cinematic photography).
// IDs have been verified live; if a future change replaces one, run
// `curl -I https://images.unsplash.com/photo-<id>` to confirm 200.
// ----------------------------------------------------------------------------
const unsplash = (id: string, w = 1600, q = 80) =>
  `https://images.unsplash.com/photo-${id}?w=${w}&q=${q}&auto=format&fit=crop`;

const PHOTO = {
  // Hero background candidates — cinematic, moody, no faces front-and-center
  hero: "1485827404703-89b55fcc595e",
  // 8 themes — each picture is intentionally evocative of the theme name
  folkloric: "1500964757637-c85e8a162699",   // mountains at dusk
  urban: "1514924013411-cbf25faa35bb",       // city night neon
  wilderness: "1448375240586-882707db888b",  // dark forest path
  memory: "1517423440428-a5a00ad493e8",      // faded portrait
  domestic: "1505691938895-1758d7feb511",    // dim interior
  travel: "1502691876148-a84978e59af8",      // empty road dusk
  tech: "1518770660439-4636190af475",        // server cables glow
  workplace: "1497366216548-37526070297c",   // empty office
  // Extras for the showcase gallery
  s1: "1466692476868-aef1dfb1e735",          // forest fog
  s2: "1500382017468-9049fed747ef",          // desert
  s3: "1542273917363-3b1817f69a2d",          // night portrait
  s4: "1462536943532-57a629f6cc60",          // mountain night
};

const THEMES = [
  { id: "folkloric",  en: "Folkloric",   ar: "فلكلوري", desc: "Ancestral tales, jinn, old wells",          photo: PHOTO.folkloric,  grad: ["#B07F1F", "#E7B53C"] },
  { id: "urban",      en: "Urban",       ar: "مدني",    desc: "City legends, late-night streets",         photo: PHOTO.urban,      grad: ["#3B82F6", "#1E40AF"] },
  { id: "wilderness", en: "Wilderness",  ar: "البرية",  desc: "Forests, deserts, the unknown",            photo: PHOTO.wilderness, grad: ["#059669", "#064E3B"] },
  { id: "memory",     en: "Memory",      ar: "الذاكرة", desc: "Psychological, half-remembered",           photo: PHOTO.memory,     grad: ["#8B5CF6", "#5B21B6"] },
  { id: "domestic",   en: "Domestic",    ar: "منزلي",   desc: "Home, family, the everyday turned",        photo: PHOTO.domestic,   grad: ["#EA580C", "#9A3412"] },
  { id: "travel",     en: "Travel",      ar: "سفر",     desc: "On the road, far from home",               photo: PHOTO.travel,     grad: ["#0D9488", "#134E4A"] },
  { id: "tech",       en: "Tech",        ar: "تقني",    desc: "Screens, signals, machines",               photo: PHOTO.tech,       grad: ["#06B6D4", "#155E75"] },
  { id: "workplace",  en: "Workplace",   ar: "العمل",   desc: "Offices, shops, after-hours",              photo: PHOTO.workplace,  grad: ["#64748B", "#334155"] },
];

const SHOWCASE = [
  { id: PHOTO.s1,         caption: "غابة الظلال",      tag: "Wilderness · 90s" },
  { id: PHOTO.folkloric,  caption: "البئر القديم",     tag: "Folkloric · 2m" },
  { id: PHOTO.urban,      caption: "شوارع منتصف الليل", tag: "Urban · 75s" },
  { id: PHOTO.s2,         caption: "صحراء الغريب",     tag: "Wilderness · 2m" },
  { id: PHOTO.memory,     caption: "ذكرى الجدة",       tag: "Memory · 90s" },
  { id: PHOTO.s3,         caption: "وجه في النافذة",   tag: "Memory · 60s" },
  { id: PHOTO.travel,     caption: "الطريق الفارغ",    tag: "Travel · 2m" },
  { id: PHOTO.s4,         caption: "ليلة على الجبل",   tag: "Folkloric · 90s" },
  { id: PHOTO.domestic,   caption: "الغرفة العلوية",   tag: "Domestic · 2m" },
];

// ============================================================================
// PAGE
// ============================================================================
export default function Page() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-hidden">
      <TopNav />
      <Hero />
      <Marquee />
      <Features />
      <Templates />
      <Showcase />
      <HowItWorks />
      <GenerationPipeline />
      <ThreeDShowcase />
      <Stats />
      <Pricing />
      <FinalCTA />
      <Footer />
    </main>
  );
}

// ============================================================================
// TOP NAV
// ============================================================================
function TopNav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "backdrop-blur-xl bg-bg/80 border-b border-white/10"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center">
        <a href="#" className="flex items-center gap-2.5 group">
          <div className="transition-transform group-hover:scale-110">
            <SparkleLogo size={32} />
          </div>
          <span className="font-bold text-lg tracking-tight">Faceless</span>
        </a>
        <nav className="hidden md:flex items-center gap-10 ml-16 text-[13px] font-medium text-muted">
          <a href="#features" className="hover:text-ink transition-colors">Features</a>
          <a href="#templates" className="hover:text-ink transition-colors">Templates</a>
          <a href="#showcase" className="hover:text-ink transition-colors">Showcase</a>
          <a href="#how" className="hover:text-ink transition-colors">How it works</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <a
            href={`${APP_URL}/`}
            className="text-[13px] font-medium text-muted hover:text-ink px-3 py-2"
          >
            Sign in
          </a>
          <a
            href={`${APP_URL}/`}
            className="group bg-accent text-bg font-semibold text-[13px] px-4 py-2 rounded-lg hover:bg-accent/90 transition-all hover:scale-[1.03] flex items-center gap-1.5"
          >
            Start free
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </a>
        </div>
      </div>
    </header>
  );
}

// ============================================================================
// HERO — full-bleed photo background with Ken-Burns zoom, gradient overlay,
//         giant overlay text. The visual hook the user wanted.
// ============================================================================
function Hero() {
  const heroRef = useRef<HTMLDivElement>(null);
  const spotX = useMotionValue(50);
  const spotY = useMotionValue(50);
  const sx = useSpring(spotX, { stiffness: 80, damping: 25 });
  const sy = useSpring(spotY, { stiffness: 80, damping: 25 });

  return (
    <section
      ref={heroRef}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        spotX.set(((e.clientX - r.left) / r.width) * 100);
        spotY.set(((e.clientY - r.top) / r.height) * 100);
      }}
      className="relative h-[100vh] min-h-[640px] overflow-hidden flex items-center"
    >
      {/* Full-bleed background photo with slow zoom (Ken Burns) */}
      <motion.div
        className="absolute inset-0"
        initial={{ scale: 1.08 }}
        animate={{ scale: 1.18 }}
        transition={{ duration: 30, ease: "linear", repeat: Infinity, repeatType: "reverse" }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={unsplash(PHOTO.hero, 2400, 80)}
          alt=""
          className="w-full h-full object-cover"
          loading="eager"
          fetchPriority="high"
        />
      </motion.div>

      {/* Dark gradient overlay for legibility */}
      <div className="absolute inset-0 bg-gradient-to-b from-bg/40 via-bg/70 to-bg" />
      <div className="absolute inset-0 bg-gradient-to-r from-bg via-bg/30 to-bg/80" />

      {/* Particle constellation — the AI signature visual */}
      <ParticleField className="absolute inset-0 opacity-70" density={70} />

      {/* Cursor-follow spotlight — radial gold glow that tracks the mouse */}
      <motion.div
        className="absolute inset-0 pointer-events-none mix-blend-screen opacity-50"
        style={{
          background: useTransform(
            [sx, sy],
            ([x, y]) =>
              `radial-gradient(450px circle at ${x}% ${y}%, rgba(231,181,60,0.25), transparent 60%)`,
          ),
        }}
      />

      {/* Floating gold/violet glow accents */}
      <motion.div
        className="absolute top-[20%] left-[10%] w-[400px] h-[400px] rounded-full blur-[120px] opacity-40 pointer-events-none"
        style={{ background: "#E7B53C" }}
        animate={{ y: [0, 30, 0], x: [0, 20, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[10%] right-[10%] w-[500px] h-[500px] rounded-full blur-[120px] opacity-30 pointer-events-none"
        style={{ background: "#8B5CF6" }}
        animate={{ y: [0, -30, 0], x: [0, -20, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Foreground content */}
      <div className="relative max-w-7xl mx-auto px-5 sm:px-8 w-full">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 mb-7 px-3.5 py-1.5 rounded-full border border-accent/40 bg-accent/10 backdrop-blur-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-accent" />
          <span className="text-[11px] font-bold text-accent tracking-[0.15em]">
            <ScrambleText text="AI-POWERED ARABIC STORYTELLING" />
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-6xl sm:text-8xl lg:text-9xl font-extrabold tracking-[-0.04em] mb-6 max-w-5xl leading-[0.95]"
        >
          One line in.
          <br />
          <span className="bg-gradient-to-br from-accent via-amber-200 to-accent2 bg-clip-text text-transparent">
            A film out.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-xl sm:text-2xl text-ink/85 mb-2 max-w-2xl font-light leading-relaxed"
        >
          Turn a one-sentence premise into a cinematic Arabic short. Script,
          voice, visuals, captions. Generated in minutes.
        </motion.p>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="text-base text-muted mb-10 font-arabic"
          dir="rtl"
        >
          من جملة واحدة إلى فيلم قصير كامل بالعربية
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex flex-col sm:flex-row gap-3 items-start sm:items-center"
        >
          <a
            href={`${APP_URL}/`}
            className="group bg-accent text-bg font-bold px-8 py-4 rounded-xl text-base flex items-center gap-2 hover:bg-accent/90 transition-all hover:scale-105 shadow-2xl shadow-accent/30"
          >
            <Sparkles className="w-4 h-4" />
            Start creating free
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="#showcase"
            className="group flex items-center gap-3 text-ink/90 hover:text-ink font-medium px-5 py-4 transition-colors"
          >
            <span className="w-11 h-11 rounded-full border border-white/30 group-hover:border-accent/60 group-hover:bg-accent/10 flex items-center justify-center transition-all">
              <Play className="w-4 h-4 fill-current ml-0.5" />
            </span>
            See examples
          </a>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.7 }}
          className="text-xs text-muted/70 tracking-[0.15em] mt-10"
        >
          FREE TO WRITE  ·  SUBSCRIBE TO RENDER  ·  NO CARD REQUIRED
        </motion.p>
      </div>

      {/* Scroll cue */}
      <motion.div
        animate={{ y: [0, 8, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-muted/60 text-xs tracking-[0.2em]"
      >
        SCROLL
        <div className="w-px h-8 bg-gradient-to-b from-muted/60 to-transparent" />
      </motion.div>
    </section>
  );
}

// ============================================================================
// MARQUEE
// ============================================================================
function Marquee() {
  const items = [
    "ARABIC NATIVE",
    "RTL DIALOGUE",
    "CINEMATIC SHOTS",
    "AUTO CAPTIONS",
    "FREE SCRIPT EXPORT",
    "8 STORY THEMES",
    "VOICE-LOCKED CHARACTERS",
    "MUSIC-MATCHED MOODS",
  ];
  const looped = [...items, ...items];
  return (
    <section className="relative py-8 border-y border-white/5 bg-surface/30 overflow-hidden">
      <div className="flex whitespace-nowrap animate-marquee gap-12 will-change-transform">
        {looped.map((it, i) => (
          <span
            key={i}
            className="text-2xl sm:text-3xl font-bold tracking-tight text-muted/40 flex items-center gap-12"
          >
            {it}
            <Sparkles className="w-5 h-5 text-accent/50" />
          </span>
        ))}
      </div>
      <style jsx>{`
        @keyframes marquee {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .animate-marquee {
          animation: marquee 40s linear infinite;
        }
      `}</style>
    </section>
  );
}

// ============================================================================
// FEATURES
// ============================================================================
function Features() {
  const items = [
    { icon: Wand2, title: "AI script writer", body: "One sentence in. A full Arabic script out — dialogue, characters, shot descriptions, ready to render." },
    { icon: Film, title: "Cinematic video", body: "Each beat becomes a clip. Characters stay consistent. Lip-synced dialogue, music, captions, mp4." },
    { icon: Languages, title: "Authentic Arabic", body: "MSA or dialect. Voice acting in Arabic, not a Western voice trying. Made for Arab audiences." },
    { icon: FileText, title: "Free PDF export", body: "Even on the free tier: take the director's-script PDF — cover page, cast list, VISUAL + DIALOGUE blocks." },
  ];
  return (
    <section id="features" className="relative py-28 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="WHAT YOU GET" />
        <SectionTitle en="An entire crew. In your pocket." ar="طاقم إنتاج كامل في جيبك" />
        <div className="mt-16 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {items.map((it, i) => (
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="group bg-surface/60 backdrop-blur-sm border border-white/10 rounded-2xl p-6 hover:border-accent/40 transition-all hover:-translate-y-1 hover:bg-surface/80"
            >
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent/25 to-accent/5 border border-accent/30 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                <it.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="font-bold text-lg mb-2 tracking-tight">{it.title}</h3>
              <p className="text-sm text-muted leading-relaxed">{it.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// TEMPLATES — 8 theme cards, each backed by a real Unsplash photo with
//             theme-colored gradient blend overlay and hover zoom.
// ============================================================================
function Templates() {
  return (
    <section id="templates" className="relative py-28 px-5 sm:px-8 bg-surface/20">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="TEMPLATES" />
        <SectionTitle en="Pick a vibe, write a line." ar="اختر الجو، اكتب الجملة" />
        <p className="mt-4 text-muted max-w-2xl">
          Eight directions to start from. The AI shapes the story around your
          premise — characters, beats, shot list, dialogue.
        </p>
        <div className="mt-12 grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {THEMES.map((t, i) => (
            <motion.a
              key={t.id}
              href={`${APP_URL}/?theme=${t.id}`}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.04 }}
              className="group block"
            >
              <TiltCard maxTilt={8} scale={1.04}>
                <ThemePoster theme={t} />
              </TiltCard>
            </motion.a>
          ))}
        </div>
      </div>
    </section>
  );
}

function ThemePoster({ theme }: { theme: (typeof THEMES)[number] }) {
  return (
    <div className="relative aspect-[3/4] rounded-2xl overflow-hidden border border-white/10 group-hover:border-white/30 transition-all group-hover:-translate-y-1 shadow-xl">
      {/* Real Unsplash photo background — slow zoom on hover */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={unsplash(theme.photo, 800, 70)}
        alt={theme.en}
        loading="lazy"
        className="absolute inset-0 w-full h-full object-cover transition-transform duration-[2500ms] group-hover:scale-110"
      />
      {/* Theme-colored gradient blend — keeps each poster on-brand */}
      <div
        className="absolute inset-0 mix-blend-soft-light opacity-90"
        style={{ background: `linear-gradient(135deg, ${theme.grad[0]}, ${theme.grad[1]})` }}
      />
      {/* Bottom vignette so text stays readable */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />
      {/* Title overlay */}
      <div className="absolute inset-0 p-5 flex flex-col justify-end">
        <div className="text-[10px] font-bold text-white/70 tracking-[0.2em] mb-1 uppercase">
          {theme.en}
        </div>
        <div className="text-2xl sm:text-3xl font-bold text-white mb-2 font-arabic tracking-tight" dir="rtl">
          {theme.ar}
        </div>
        <p className="text-xs text-white/80 leading-snug line-clamp-2">
          {theme.desc}
        </p>
      </div>
      <div className="absolute top-4 right-4 w-9 h-9 rounded-full bg-black/50 backdrop-blur-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all group-hover:scale-110">
        <ArrowRight className="w-4 h-4 text-white" />
      </div>
    </div>
  );
}

// ============================================================================
// SHOWCASE — masonry-style photo gallery; the "what you can make" visual proof
// ============================================================================
function Showcase() {
  return (
    <section id="showcase" className="relative py-28 px-5 sm:px-8 overflow-hidden">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="THE LIBRARY" />
        <SectionTitle en="Cinema-grade stories." ar="قصص بجودة سينمائية" />
        <p className="mt-4 text-muted max-w-2xl">
          Each scene rendered as a vertical clip — characters consistent, voices
          in Arabic, captions baked in. Ready to drop on TikTok, Reels, Shorts.
        </p>

        {/* Masonry-style grid — varies tile heights for visual rhythm */}
        <div className="mt-14 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
          {SHOWCASE.map((s, i) => (
            <ShowcaseTile key={i} item={s} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}

function ShowcaseTile({
  item,
  index,
}: {
  item: (typeof SHOWCASE)[number];
  index: number;
}) {
  // Mix of 9:16 (3) and 3:4 (1) aspect ratios to create the masonry feel
  const tall = index % 3 !== 1;
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-30px" }}
      transition={{ duration: 0.5, delay: (index % 4) * 0.06 }}
      className={`${tall ? "aspect-[9/16]" : "aspect-[3/4]"}`}
    >
    <TiltCard maxTilt={10} scale={1.04} className={`relative w-full h-full rounded-2xl overflow-hidden group cursor-pointer border border-white/10 hover:border-accent/40 transition-all`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={unsplash(item.id, 600, 70)}
        alt={item.caption}
        loading="lazy"
        className="absolute inset-0 w-full h-full object-cover transition-transform duration-[2000ms] group-hover:scale-110"
      />
      {/* Vignette */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent" />
      {/* Play overlay on hover */}
      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="w-14 h-14 rounded-full bg-accent/90 flex items-center justify-center scale-90 group-hover:scale-100 transition-transform">
          <Play className="w-5 h-5 text-bg fill-current ml-0.5" />
        </div>
      </div>
      {/* Caption */}
      <div className="absolute inset-x-0 bottom-0 p-3 sm:p-4">
        <div className="text-[10px] font-bold text-white/70 tracking-[0.18em] mb-1 uppercase">
          {item.tag}
        </div>
        <div className="text-sm sm:text-base font-bold text-white font-arabic" dir="rtl">
          {item.caption}
        </div>
      </div>
    </TiltCard>
    </motion.div>
  );
}

// ============================================================================
// HOW IT WORKS
// ============================================================================
function HowItWorks() {
  const steps = [
    { step: "01", title: "Write a premise", body: "One sentence is enough. The shorter, the better.", detail: "Free · no card" },
    { step: "02", title: "AI writes your script", body: "Beats, characters, dialogue, shot directions. Arabic. Seconds.", detail: "Free · download PDF" },
    { step: "03", title: "Render the video", body: "Each beat becomes a clip. Stitched with music and captions.", detail: "1 credit per clip" },
  ];
  return (
    <section id="how" className="relative py-28 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="HOW IT WORKS" />
        <SectionTitle en="Three steps. No editing required." ar="ثلاث خطوات بلا مونتاج" />
        <div className="mt-16 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <motion.div
              key={s.step}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.12 }}
              className="relative"
            >
              <div className="relative bg-gradient-to-br from-surface to-surface/40 border border-white/10 rounded-2xl p-7 h-full hover:border-accent/30 transition-colors overflow-hidden">
                <div className="absolute -top-4 -right-4 text-[120px] font-black text-white/[0.04] leading-none select-none">
                  {s.step}
                </div>
                <div className="relative">
                  <div className="text-accent font-bold text-sm tracking-[0.2em] mb-4">
                    STEP {s.step}
                  </div>
                  <h3 className="text-2xl font-bold mb-3 tracking-tight">
                    {s.title}
                  </h3>
                  <p className="text-muted leading-relaxed mb-6">{s.body}</p>
                  <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent/80 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20">
                    <CheckCircle2 className="w-3 h-3" />
                    {s.detail}
                  </div>
                </div>
              </div>
              {i < steps.length - 1 && (
                <div className="hidden lg:block absolute top-1/2 -right-4 z-10 transform -translate-y-1/2">
                  <ArrowRight className="w-6 h-6 text-muted/40" />
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// 3D SHOWCASE — perspective-tilted card fan with parallax depth
// ============================================================================
function ThreeDShowcase() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });

  const left = useTransform(scrollYProgress, [0, 1], [200, -200]);
  const right = useTransform(scrollYProgress, [0, 1], [200, -200]);
  const center = useTransform(scrollYProgress, [0, 1], [100, -100]);
  const leftRot = useTransform(scrollYProgress, [0, 1], [-30, 30]);
  const rightRot = useTransform(scrollYProgress, [0, 1], [30, -30]);

  return (
    <section ref={ref} className="relative py-32 px-5 sm:px-8 overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(139,92,246,0.2), transparent 70%)",
        }}
      />
      <div className="relative max-w-7xl mx-auto">
        <SectionEyebrow text="EVERY BEAT, A CLIP" />
        <SectionTitle en="See it move." ar="شاهدها تتحرك" />
        <p className="mt-4 text-muted max-w-2xl">
          Each beat is rendered as a cinematic clip — then stitched, scored,
          captioned, and ready to share.
        </p>

        <div
          className="mt-20 relative h-[520px] flex items-center justify-center"
          style={{ perspective: "1800px" }}
        >
          <motion.div
            style={{
              y: left,
              rotateY: leftRot,
              rotateZ: -10,
              x: -180,
              transformStyle: "preserve-3d",
            }}
            className="absolute w-60 aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border border-white/20"
          >
            <ThemePoster theme={THEMES[0]} />
          </motion.div>
          <motion.div
            style={{ y: center, transformStyle: "preserve-3d" }}
            className="absolute w-72 aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border-2 border-accent/50 z-10"
          >
            <ThemePoster theme={THEMES[3]} />
          </motion.div>
          <motion.div
            style={{
              y: right,
              rotateY: rightRot,
              rotateZ: 10,
              x: 180,
              transformStyle: "preserve-3d",
            }}
            className="absolute w-60 aspect-[9/16] rounded-2xl overflow-hidden shadow-2xl border border-white/20"
          >
            <ThemePoster theme={THEMES[6]} />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STATS
// ============================================================================
function Stats() {
  const stats = [
    { value: 60, suffix: "+", label: "clips per month on Creator" },
    { value: 9, suffix: ":16", label: "vertical, ready for shorts" },
    { value: 8, suffix: "", label: "story themes to start from" },
    { value: 1, suffix: "", label: "credit per clip · no surprises" },
  ];
  return (
    <section className="relative py-24 px-5 sm:px-8 border-y border-white/5 bg-surface/20">
      <div className="max-w-7xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((s, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
          >
            <div className="text-5xl sm:text-6xl font-extrabold tracking-tight">
              <CountUp end={s.value} />
              <span className="text-accent">{s.suffix}</span>
            </div>
            <div className="mt-2 text-sm text-muted leading-tight">
              {s.label}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function CountUp({ end }: { end: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const duration = 1100;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(end * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, end]);
  return <span ref={ref}>{value}</span>;
}

// ============================================================================
// PRICING
// ============================================================================
function Pricing() {
  const tiers = [
    { name: "Starter", price: "$9", credits: 12, blurb: "For trying ideas", perks: ["12 video clips/mo", "All themes", "Free PDF export"] },
    { name: "Creator", price: "$29", credits: 60, blurb: "For weekly drops", recommended: true, perks: ["60 video clips/mo", "Priority rendering", "All themes", "Free PDF export"] },
    { name: "Pro", price: "$79", credits: 200, blurb: "For daily output", perks: ["200 video clips/mo", "Priority rendering", "All themes", "Free PDF export"] },
  ];
  return (
    <section id="pricing" className="relative py-28 px-5 sm:px-8">
      <div className="max-w-6xl mx-auto">
        <SectionEyebrow text="PRICING" />
        <SectionTitle en="Subscribe once. Render every month." ar="اشترك مرة، ارند كل شهر" />
        <p className="mt-4 text-muted max-w-2xl">
          1 credit = 1 video clip. Pause or change tier any time.
        </p>
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-5">
          {tiers.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className={`relative rounded-2xl p-8 border transition-all ${
                t.recommended
                  ? "bg-gradient-to-b from-accent/15 to-transparent border-accent/50 lg:scale-[1.04]"
                  : "bg-surface/40 border-white/10 hover:border-white/25"
              }`}
            >
              {t.recommended && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-accent text-bg text-[10px] font-bold tracking-[0.15em]">
                  RECOMMENDED
                </div>
              )}
              <h3 className="text-xl font-bold mb-1">{t.name}</h3>
              <div className="text-sm text-muted mb-5">{t.blurb}</div>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="text-5xl font-extrabold text-accent tracking-tight">{t.price}</span>
                <span className="text-muted">/ month</span>
              </div>
              <ul className="space-y-2.5 mb-7">
                {t.perks.map((p) => (
                  <li key={p} className="flex items-center gap-2 text-sm text-ink/90">
                    <CheckCircle2 className="w-4 h-4 text-accent flex-shrink-0" />
                    {p}
                  </li>
                ))}
              </ul>
              <a
                href={`${APP_URL}/`}
                className={`block text-center font-bold py-3 rounded-xl transition-all ${
                  t.recommended
                    ? "bg-accent text-bg hover:bg-accent/90 hover:scale-[1.02]"
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

// ============================================================================
// FINAL CTA — full-bleed photo + concentric rotating rings
// ============================================================================
function FinalCTA() {
  return (
    <section className="relative py-32 px-5 sm:px-8 overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={unsplash(PHOTO.s4, 2000, 70)}
        alt=""
        className="absolute inset-0 w-full h-full object-cover opacity-30"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-bg via-bg/60 to-bg" />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(231,181,60,0.3), transparent 60%)",
        }}
      />
      <motion.div
        animate={{ rotate: [0, 360] }}
        transition={{ duration: 120, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30"
      >
        <div className="w-[800px] h-[800px] rounded-full border border-accent/30" />
      </motion.div>
      <motion.div
        animate={{ rotate: [0, -360] }}
        transition={{ duration: 90, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-40"
      >
        <div className="w-[500px] h-[500px] rounded-full border border-accent/40" />
      </motion.div>
      <div className="relative max-w-3xl mx-auto text-center">
        <div className="inline-flex justify-center mb-8">
          <SparkleLogo size={80} />
        </div>
        <h2 className="text-5xl sm:text-7xl font-extrabold mb-6 tracking-[-0.04em]">
          Your first story
          <br />
          <span className="bg-gradient-to-br from-accent via-amber-200 to-accent2 bg-clip-text text-transparent">
            is free.
          </span>
        </h2>
        <p className="text-lg sm:text-xl text-muted mb-10 max-w-xl mx-auto">
          Write one line. Get a full Arabic script back in seconds. Render it
          whenever you're ready.
        </p>
        <a
          href={`${APP_URL}/`}
          className="inline-flex items-center gap-2 bg-accent text-bg font-bold px-9 py-4 rounded-xl text-base hover:bg-accent/90 transition-all hover:scale-105 shadow-2xl shadow-accent/30"
        >
          <Zap className="w-4 h-4" />
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
    <footer className="border-t border-white/5 py-12 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center gap-5">
        <div className="flex items-center gap-2.5">
          <SparkleLogo size={28} />
          <span className="text-sm text-muted">Faceless · made for Arabic storytellers</span>
        </div>
        <div className="sm:ml-auto flex items-center gap-7 text-[13px] text-muted">
          <a href="#features" className="hover:text-ink transition-colors">Features</a>
          <a href="#templates" className="hover:text-ink transition-colors">Templates</a>
          <a href="#showcase" className="hover:text-ink transition-colors">Showcase</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href={`${APP_URL}/`} className="hover:text-ink transition-colors">Sign in</a>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// SHARED
// ============================================================================
function SectionEyebrow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="w-8 h-px bg-accent" />
      <span className="text-[11px] font-bold text-accent tracking-[0.2em]">
        {text}
      </span>
    </div>
  );
}

function SectionTitle({ en, ar }: { en: string; ar: string }) {
  return (
    <div className="flex items-baseline gap-3 flex-wrap">
      <h2 className="text-4xl sm:text-6xl font-extrabold tracking-[-0.03em]">
        {en}
      </h2>
      <span
        className="text-xl sm:text-2xl text-muted/70 font-arabic tracking-tight"
        dir="rtl"
      >
        {ar}
      </span>
    </div>
  );
}

