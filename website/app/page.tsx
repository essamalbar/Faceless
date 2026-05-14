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

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  "https://faceless-api-uplzdtffeq-uc.a.run.app";

// ----------------------------------------------------------------------------
// THEME CATALOG — templates the visitor can imagine starting from on day one.
// Mirror of lib/screens/home_screen.dart's _allThemes.
// ----------------------------------------------------------------------------
const THEMES = [
  { id: "folkloric", en: "Folkloric", ar: "فلكلوري", desc: "Ancestral tales, jinn, old wells", grad: ["#B07F1F", "#E7B53C"] },
  { id: "urban", en: "Urban", ar: "مدني", desc: "City legends, late-night streets", grad: ["#3B82F6", "#1E40AF"] },
  { id: "wilderness", en: "Wilderness", ar: "البرية", desc: "Forests, deserts, the unknown", grad: ["#059669", "#064E3B"] },
  { id: "memory", en: "Memory", ar: "الذاكرة", desc: "Psychological, half-remembered", grad: ["#8B5CF6", "#5B21B6"] },
  { id: "domestic", en: "Domestic", ar: "منزلي", desc: "Home, family, the everyday turned", grad: ["#EA580C", "#9A3412"] },
  { id: "travel", en: "Travel", ar: "سفر", desc: "On the road, far from home", grad: ["#0D9488", "#134E4A"] },
  { id: "tech", en: "Tech", ar: "تقني", desc: "Screens, signals, machines", grad: ["#06B6D4", "#155E75"] },
  { id: "workplace", en: "Workplace", ar: "العمل", desc: "Offices, shops, after-hours", grad: ["#64748B", "#334155"] },
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
      <HowItWorks />
      <ThreeDShowcase />
      <Stats />
      <Pricing />
      <FinalCTA />
      <Footer />
    </main>
  );
}

// ============================================================================
// TOP NAV  — translucent, blurred, glass-effect
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
// HERO  — gradient mesh background, floating orbs, sparkle logo
// ============================================================================
function Hero() {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const x = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const y = useSpring(mouseY, { stiffness: 50, damping: 20 });

  return (
    <section
      className="relative pt-36 sm:pt-44 pb-24 sm:pb-32 px-5 sm:px-8 overflow-hidden min-h-[100vh] flex items-center"
      onMouseMove={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        mouseX.set((e.clientX - rect.left - rect.width / 2) / 30);
        mouseY.set((e.clientY - rect.top - rect.height / 2) / 30);
      }}
    >
      <GradientMesh x={x} y={y} />

      <div className="relative max-w-5xl mx-auto text-center w-full">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 mb-8 px-3.5 py-1.5 rounded-full border border-accent/30 bg-accent/10 backdrop-blur-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-accent" />
          <span className="text-[11px] font-bold text-accent tracking-[0.15em]">
            AI-POWERED ARABIC STORYTELLING
          </span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="mb-8 flex justify-center"
        >
          <div className="relative">
            <div
              className="absolute inset-0 blur-3xl opacity-60"
              style={{ background: "#E7B53C" }}
            />
            <motion.div
              animate={{ rotate: [0, 360] }}
              transition={{ duration: 80, repeat: Infinity, ease: "linear" }}
              className="relative"
            >
              <SparkleLogo size={112} />
            </motion.div>
          </div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-6xl sm:text-8xl font-extrabold tracking-[-0.04em] mb-6"
        >
          One line in.{" "}
          <span className="bg-gradient-to-br from-accent via-amber-300 to-accent2 bg-clip-text text-transparent">
            A film out.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-xl sm:text-2xl text-ink/80 mb-3 max-w-3xl mx-auto font-light"
        >
          Turn a one-sentence premise into a cinematic Arabic short — script,
          voice, visuals, captions. Done.
        </motion.p>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="text-base text-muted mb-12 font-arabic"
          dir="rtl"
        >
          من جملة واحدة إلى فيلم قصير كامل بالعربية
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex flex-col sm:flex-row gap-3 justify-center items-center mb-6"
        >
          <a
            href={`${APP_URL}/`}
            className="group bg-accent text-bg font-bold px-8 py-4 rounded-xl text-base flex items-center gap-2 hover:bg-accent/90 transition-all hover:scale-105 shadow-2xl shadow-accent/20"
          >
            <Sparkles className="w-4 h-4" />
            Start creating free
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="#templates"
            className="group flex items-center gap-2 text-muted hover:text-ink font-medium px-5 py-4 transition-colors"
          >
            <span className="w-9 h-9 rounded-full border border-white/20 group-hover:border-accent/50 flex items-center justify-center transition-colors">
              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
            </span>
            See examples
          </a>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.7 }}
          className="text-xs text-muted/60 tracking-[0.1em]"
        >
          FREE TO WRITE  ·  SUBSCRIBE TO RENDER  ·  NO CARD REQUIRED
        </motion.p>
      </div>
    </section>
  );
}

// Animated multi-layer gradient mesh — the visual replacement for a hero
// video. Three large radial blobs in motion + a faint noise overlay gives
// the feel of a constantly-morphing AI energy field. Cheap (GPU-only
// transforms), runs at 60fps on phones.
function GradientMesh({
  x,
  y,
}: {
  x: ReturnType<typeof useSpring>;
  y: ReturnType<typeof useSpring>;
}) {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      <motion.div
        className="absolute top-[10%] left-[15%] w-[600px] h-[600px] rounded-full blur-[120px] opacity-50"
        style={{ background: "#E7B53C", x, y }}
        animate={{
          scale: [1, 1.15, 1],
          x: [0, 60, -40, 0],
          y: [0, -40, 30, 0],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute top-[40%] right-[10%] w-[500px] h-[500px] rounded-full blur-[120px] opacity-40"
        style={{ background: "#8B5CF6" }}
        animate={{
          scale: [1, 1.2, 1],
          x: [0, -80, 40, 0],
          y: [0, 60, -30, 0],
        }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[5%] left-[40%] w-[700px] h-[700px] rounded-full blur-[140px] opacity-30"
        style={{ background: "#3B82F6" }}
        animate={{
          scale: [1, 1.1, 1],
          x: [0, 40, -50, 0],
          y: [0, -50, 20, 0],
        }}
        transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
      />
      {/* Grain overlay — fine noise via SVG keeps the gradient from
          looking like plastic. Tiny inline SVG, no external request. */}
      <div
        className="absolute inset-0 opacity-[0.08] mix-blend-overlay pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
}

// ============================================================================
// MARQUEE  — infinite scroll strip below the hero, like artlist.io
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
  // Render the list twice so the loop is seamless
  const looped = [...items, ...items];
  return (
    <section className="relative py-10 border-y border-white/5 bg-surface/30 overflow-hidden">
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
    { icon: Film, title: "Cinematic video", body: "Each beat becomes a clip. Characters stay consistent. Lip-synced dialogue, music, captions stitched into a final mp4." },
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
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-accent/20 to-accent/5 border border-accent/30 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
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
// TEMPLATES  — 8 animated theme posters
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
              <ThemePoster theme={t} />
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
      {/* Animated gradient base */}
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(135deg, ${theme.grad[0]}, ${theme.grad[1]})`,
        }}
      />
      {/* Slow-shifting overlay — gives the poster motion without needing a video */}
      <motion.div
        className="absolute inset-0 mix-blend-overlay opacity-40"
        animate={{
          background: [
            `radial-gradient(at 20% 20%, ${theme.grad[1]} 0%, transparent 50%)`,
            `radial-gradient(at 80% 60%, ${theme.grad[0]} 0%, transparent 50%)`,
            `radial-gradient(at 30% 80%, ${theme.grad[1]} 0%, transparent 50%)`,
            `radial-gradient(at 20% 20%, ${theme.grad[1]} 0%, transparent 50%)`,
          ],
        }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      {/* Drifting sparkles */}
      <PosterSparkles />
      {/* Bottom-to-top vignette so text is readable */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
      {/* Title overlay */}
      <div className="absolute inset-0 p-5 flex flex-col justify-end">
        <div className="text-[10px] font-bold text-white/70 tracking-[0.2em] mb-1 uppercase">
          {theme.en}
        </div>
        <div
          className="text-2xl sm:text-3xl font-bold text-white mb-2 font-arabic tracking-tight"
          dir="rtl"
        >
          {theme.ar}
        </div>
        <p className="text-xs text-white/75 leading-snug line-clamp-2">
          {theme.desc}
        </p>
      </div>
      {/* Hover arrow */}
      <div className="absolute top-4 right-4 w-9 h-9 rounded-full bg-black/40 backdrop-blur-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all group-hover:scale-110">
        <ArrowRight className="w-4 h-4 text-white" />
      </div>
    </div>
  );
}

function PosterSparkles() {
  // Four staggered drifting sparkles — pure CSS keyframes via inline style.
  // Random-ish positions baked at build time (not runtime) so SSR stays stable.
  const positions = [
    { left: "15%", top: "20%", delay: "0s" },
    { left: "80%", top: "30%", delay: "1.5s" },
    { left: "25%", top: "70%", delay: "3s" },
    { left: "70%", top: "85%", delay: "4.5s" },
  ];
  return (
    <>
      {positions.map((p, i) => (
        <div
          key={i}
          className="absolute w-1 h-1 rounded-full bg-white"
          style={{
            left: p.left,
            top: p.top,
            animation: `twinkle 6s ease-in-out ${p.delay} infinite`,
            boxShadow: "0 0 8px rgba(255,255,255,0.8)",
          }}
        />
      ))}
      <style jsx>{`
        @keyframes twinkle {
          0%, 100% { opacity: 0; transform: scale(0.5); }
          50% { opacity: 1; transform: scale(1.5); }
        }
      `}</style>
    </>
  );
}

// ============================================================================
// HOW IT WORKS  — 3 step animated diagram
// ============================================================================
function HowItWorks() {
  const steps = [
    {
      step: "01",
      title: "Write a premise",
      body: "One sentence is enough. The shorter, the better.",
      detail: "Free · no card",
    },
    {
      step: "02",
      title: "AI writes your script",
      body: "Beats, characters, dialogue, shot directions. Arabic. Seconds.",
      detail: "Free · download PDF",
    },
    {
      step: "03",
      title: "Render the video",
      body: "Each beat becomes a clip. Stitched with music and captions.",
      detail: "1 credit per clip",
    },
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
                {/* Big translucent step number behind */}
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
// 3D SHOWCASE  — perspective-tilted card fan with parallax depth
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
// STATS  — big numbers with count-up on enter
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

// Lightweight count-up that runs when the element enters the viewport.
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
      // Ease-out cubic
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
// FINAL CTA
// ============================================================================
function FinalCTA() {
  return (
    <section className="relative py-32 px-5 sm:px-8 overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(231,181,60,0.25), transparent 60%)",
        }}
      />
      <motion.div
        animate={{ rotate: [0, 360] }}
        transition={{ duration: 120, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30"
      >
        <div className="w-[800px] h-[800px] rounded-full border border-accent/20" />
      </motion.div>
      <motion.div
        animate={{ rotate: [0, -360] }}
        transition={{ duration: 90, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-40"
      >
        <div className="w-[500px] h-[500px] rounded-full border border-accent/30" />
      </motion.div>
      <div className="relative max-w-3xl mx-auto text-center">
        <div className="inline-flex justify-center mb-8">
          <SparkleLogo size={72} />
        </div>
        <h2 className="text-5xl sm:text-7xl font-extrabold mb-6 tracking-[-0.04em]">
          Your first story
          <br />
          <span className="bg-gradient-to-br from-accent via-amber-300 to-accent2 bg-clip-text text-transparent">
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
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href={`${APP_URL}/`} className="hover:text-ink transition-colors">Sign in</a>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// SHARED — section header bits
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
