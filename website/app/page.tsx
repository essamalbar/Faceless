"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import {
  Sparkles,
  Wand2,
  Film,
  Languages,
  FileText,
  ArrowRight,
  CheckCircle2,
  Play,
  ShieldCheck,
  Eye,
  RotateCcw,
  Users,
} from "lucide-react";
import { SparkleLogo } from "@/components/sparkle-logo";
import { LazyVideo } from "@/components/lazy-video";
import { PromptInput } from "@/components/prompt-input";
import { Aurora } from "@/components/aurora";
import { ScrollPipeline } from "@/components/scroll-pipeline";
import { useEffect, useState } from "react";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  "https://app.faceless-lab.com";

// ----------------------------------------------------------------------------
// All atmospheric clips come from Mixkit's free-stock library (CC0,
// commercial use OK). IDs scraped from their cinematic / mystery / dark /
// alone / walking / silhouette / shadow / atmospheric categories so the
// content matches the brand. URL pattern:
//   https://assets.mixkit.co/videos/<id>/<id>-720.mp4
// ----------------------------------------------------------------------------
const mp4 = (id: number) =>
  `https://assets.mixkit.co/videos/${id}/${id}-720.mp4`;

const HERO_VIDEO = mp4(30605); // night / atmospheric hero loop

const THEMES = [
  { id: "folkloric",  en: "Folkloric",  ar: "فلكلوري", vid: 5565,  blurb: "Ancestral tales, myths, old traditions" },
  { id: "memory",     en: "Memory",     ar: "الذاكرة", vid: 46147, blurb: "Psychological, half-remembered" },
  { id: "wilderness", en: "Wilderness", ar: "البرية",  vid: 46138, blurb: "Forests, deserts, the unknown" },
  { id: "urban",      en: "Urban",      ar: "مدني",   vid: 30563, blurb: "City legends, late-night streets" },
  { id: "domestic",   en: "Domestic",   ar: "منزلي",  vid: 35889, blurb: "Home, family, the everyday turned" },
  { id: "travel",     en: "Travel",     ar: "سفر",    vid: 23410, blurb: "On the road, far from home" },
];

// Showreel — six hand-picked clips, one per category. Was 9; the
// section read cluttered. Six gives the masonry enough visual variety
// without overwhelming. Final "View full library →" link offers the
// rest for visitors who want to keep browsing.
const SHOWREEL = [
  { vid: 47442, caption: "البئر المهجور",      tag: "2m",   category: "folkloric",  ratio: "tall"   as const },
  { vid: 46702, caption: "وحيدًا في الليل",    tag: "90s",  category: "memory",     ratio: "tall"   as const },
  { vid: 9582,  caption: "ضوء بعيد",            tag: "75s",  category: "wilderness", ratio: "medium" as const },
  { vid: 35426, caption: "ظل في الزقاق",       tag: "90s",  category: "urban",      ratio: "medium" as const },
  { vid: 23818, caption: "صوت من الجدار",      tag: "60s",  category: "domestic",   ratio: "tall"   as const },
  { vid: 25896, caption: "الطريق الفارغ",      tag: "2m",   category: "travel",     ratio: "tall"   as const },
];

const FILTERS = [
  { id: "all",        label: "All" },
  { id: "folkloric",  label: "Folkloric" },
  { id: "memory",     label: "Memory" },
  { id: "wilderness", label: "Wilderness" },
  { id: "urban",      label: "Urban" },
  { id: "domestic",   label: "Domestic" },
  { id: "travel",     label: "Travel" },
];

// ============================================================================
// PAGE
// ============================================================================
export default function Page() {
  // Use `overflow-x-clip` (not `overflow-x-hidden`) on <main>: `hidden`
  // makes the element a scroll container which silently breaks
  // `position: sticky` on any descendant — the ScrollPipeline section
  // relies on sticky. `clip` crops the same way without establishing
  // a scroll context.
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip">
      <Nav />
      <Hero />
      <ScrollPipeline />
      <Showreel />
      <WhyFaceless />
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
        <a
          href="#"
          aria-label="Faceless Lab — home"
          className="flex items-center gap-2.5"
        >
          <SparkleLogo size={28} />
          <span className="font-semibold text-[15px] tracking-tight">
            Faceless Lab
          </span>
        </a>
        <nav
          aria-label="Primary"
          className="hidden md:flex items-center gap-7 ml-12 text-[13px] text-muted"
        >
          <a href="#why" className="hover:text-ink transition-colors">Why us</a>
          <a href="#showreel" className="hover:text-ink transition-colors">Showreel</a>
          <a href="#templates" className="hover:text-ink transition-colors">Templates</a>
          <a href="#pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href="/about" className="hover:text-ink transition-colors">About</a>
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
  // Scroll-driven parallax: the video drifts down at half speed (depth
  // illusion), the content drifts up + fades out as you scroll past.
  // Leonardo's hero feels alive scrolling because foreground and
  // background move at different rates.
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], ["0%", "-15%"]);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.85], [1, 0]);

  return (
    <section
      ref={ref}
      className="relative h-[100vh] min-h-[640px] overflow-hidden flex items-center"
    >
      {/* Full-bleed looping video, parallaxed downward at half scroll
          speed for depth */}
      <motion.div
        className="absolute inset-0"
        style={{ y: bgY }}
        aria-hidden="true"
      >
        {/* Decorative hero video. `preload="metadata"` (not "auto") so
            the browser fetches the keyframe/duration but defers the
            full payload until the video element actually mounts. With
            preload="auto" the bytes raced with the H1's text+font for
            mobile bandwidth and pushed LCP past 2.5s. */}
        <LazyVideo
          src={HERO_VIDEO}
          className="w-full h-full"
          rootMargin="0px"
          preload="metadata"
        />
      </motion.div>
      {/* Layered overlays for legibility */}
      <div className="absolute inset-0 bg-gradient-to-b from-bg/30 via-bg/60 to-bg" />
      <div className="absolute inset-0 bg-gradient-to-r from-bg/80 via-bg/30 to-transparent" />

      {/* Aurora — flowing gradient mesh, parallaxed at a third speed
          so it feels "deeper" than the foreground content */}
      <motion.div className="absolute inset-0" style={{ y: useTransform(scrollYProgress, [0, 1], ["0%", "10%"]) }}>
        <Aurora intensity={0.4} />
      </motion.div>

      <motion.div
        style={{ y: contentY, opacity: contentOpacity }}
        className="relative max-w-7xl mx-auto px-5 sm:px-8 w-full"
      >
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 mb-6 px-3 py-1 rounded-full border border-white/15 bg-black/40 backdrop-blur-sm text-[11px] tracking-wide"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          AI Arabic songs + short videos
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
          className="text-[52px] sm:text-7xl lg:text-[100px] font-semibold tracking-[-0.045em] leading-[0.96] max-w-5xl mb-7"
        >
          Two modes.
          <br />
          <span className="bg-gradient-to-br from-accent via-amber-200 to-accent2 bg-clip-text text-transparent">
            One Arabic studio.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg sm:text-xl text-ink/85 max-w-2xl mb-3 leading-relaxed"
        >
          <strong className="text-ink">Short videos:</strong> Faceless Lab
          writes the Arabic script, casts the characters, voices them in your
          dialect, and renders the video.{" "}
          <strong className="text-ink">AI songs:</strong> a theme becomes a
          full Arabic ballad with Suno V5 vocals and matching cover art.
          Preview before you spend. Refund on failure.
        </motion.p>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          // Bumped from text-muted/80 → text-ink/75 to clear WCAG AA
          // contrast on this dark gradient overlay (the previous
          // muted-with-opacity measured ~3.2:1, below the 4.5:1 floor).
          className="text-base text-ink/75 max-w-xl mb-10 font-arabic"
          dir="rtl"
          lang="ar"
        >
          استوديو عربي بوضعَين: فيديوهات قصيرة وأغانٍ كاملة — راجع الناتج قبل أن تدفع
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mb-5"
        >
          <PromptInput appUrl={APP_URL} />
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.55 }}
          className="flex items-center gap-5 text-[12px] text-muted/80"
        >
          <a href="#showreel" className="group flex items-center gap-2 hover:text-ink transition-colors">
            <span className="w-7 h-7 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 group-hover:bg-white/15 flex items-center justify-center transition-colors">
              <Play className="w-3 h-3 fill-current ml-0.5" />
            </span>
            Watch the showreel
          </a>
          <span className="text-muted/40">·</span>
          <span>Free to draft. Subscribe to generate.</span>
        </motion.div>
      </motion.div>

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
// SHOWREEL — Leonardo-style masonry gallery with filter pills above.
// Mixed tile heights (tall = 9:16, medium = 4:5) so the grid reads as
// curated rather than a strict spreadsheet.
// ============================================================================
function Showreel() {
  const [filter, setFilter] = useState("all");
  const visible = SHOWREEL.filter(
    (s) => filter === "all" || s.category === filter,
  );
  return (
    <section id="showreel" className="relative py-20 sm:py-24 border-t border-white/[0.05] overflow-hidden">
      <Aurora intensity={0.18} />
      <div className="relative max-w-7xl mx-auto px-5 sm:px-8">
        <div className="flex items-end justify-between gap-6 flex-wrap mb-10">
          <div>
            <SectionEyebrow text="THE LIBRARY" />
            <SectionTitle en="Stories rendered." ar="قصص جاهزة" />
            <p className="mt-4 text-muted max-w-xl">
              Every clip below was rendered from a one-line premise.
              Characters and voices stay locked across beats.
            </p>
          </div>
          {/* See-more link sits in the header for desktop visitors who
              want to skip the gallery and go straight to the app. */}
          <a
            href={`${APP_URL}/`}
            className="group hidden sm:inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink transition-colors"
          >
            View the full library
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </a>
        </div>

        {/* Filter pills — tighter and quieter than before */}
        <div className="flex flex-wrap gap-1.5 mb-10">
          {FILTERS.map((f) => {
            const active = f.id === filter;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                aria-pressed={active}
                aria-label={`Filter showreel by ${f.label}`}
                className={`text-[12px] font-medium px-3 py-1.5 rounded-full border transition-colors ${
                  active
                    ? "bg-ink text-bg border-ink"
                    : "bg-transparent text-muted border-white/10 hover:text-ink hover:border-white/25"
                }`}
              >
                {f.label}
              </button>
            );
          })}
        </div>

        {/* Masonry — CSS multi-column for Pinterest-style variable height */}
        <div className="masonry" style={{ columnGap: "1rem" }}>
          {visible.map((s, i) => (
            <ShowreelTile key={`${filter}-${s.vid}`} item={s} index={i} />
          ))}
        </div>

        {/* Mobile see-more link — appears below the grid since the
            header version is hidden on small screens */}
        <div className="mt-10 sm:hidden">
          <a
            href={`${APP_URL}/`}
            className="group inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink transition-colors"
          >
            View the full library
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </a>
        </div>

        <style jsx>{`
          .masonry {
            /* Default to 2 columns on mobile — 1 column made each tile
               huge and felt empty/repetitive. With 6 clips total, 2×3
               packs neatly into a single phone screen. */
            column-count: 2;
            column-gap: 0.75rem;
          }
          @media (min-width: 640px) {
            .masonry { column-count: 2; column-gap: 1rem; }
          }
          @media (min-width: 1024px) {
            .masonry { column-count: 3; column-gap: 1rem; }
          }
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
  // Tall = 9:16, medium = 4:5 — mixed aspect ratios are what makes the
  // masonry read as gallery-curated rather than a rigid grid.
  const aspect = item.ratio === "tall" ? "aspect-[9/16]" : "aspect-[4/5]";
  return (
    <motion.a
      href={`${APP_URL}/`}
      aria-label={`Open Faceless Lab — ${item.category} showreel clip (${item.tag})`}
      initial={{ opacity: 0, y: 36, filter: "blur(8px)", scale: 0.96 }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)", scale: 1 }}
      viewport={{ once: true, margin: "-30px" }}
      transition={{
        duration: 0.8,
        delay: (index % 4) * 0.09,
        ease: [0.16, 1, 0.3, 1],
      }}
      className="group relative block mb-4 overflow-hidden rounded-2xl border border-white/10 hover:border-accent/60 hover:scale-[1.02] hover:shadow-[0_0_60px_rgba(231,181,60,0.18)] transition-all duration-300 break-inside-avoid"
      style={{ breakInside: "avoid" }}
    >
      <div className={`${aspect} relative`}>
        <LazyVideo
          src={mp4(item.vid)}
          className="absolute inset-0 w-full h-full"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
        {/* Soft top inner glow on hover */}
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
             style={{ background: "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(231,181,60,0.18), transparent 60%)" }} />
        <div className="absolute inset-0 p-2.5 sm:p-4 flex flex-col justify-end">
          <div className="flex items-center gap-1.5 sm:gap-2 mb-1 sm:mb-1.5">
            <span className="text-[8px] sm:text-[9px] font-bold text-white/80 tracking-[0.15em] sm:tracking-[0.18em] uppercase px-1.5 sm:px-2 py-0.5 rounded-full bg-black/40 backdrop-blur-sm border border-white/15">
              {item.category}
            </span>
            <span className="text-[9px] sm:text-[10px] text-white/85 tracking-wider">
              {item.tag}
            </span>
          </div>
          <div
            className="text-sm sm:text-lg font-semibold text-white font-arabic tracking-tight leading-snug"
            dir="rtl"
            lang="ar"
          >
            {item.caption}
          </div>
        </div>
        <div className="absolute top-2 right-2 sm:top-3 sm:right-3 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-black/50 backdrop-blur-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <ArrowRight className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-white" />
        </div>
      </div>
    </motion.a>
  );
}

// ============================================================================
// WHY FACELESS — the four differentiators competitors don't have. These
// are the load-bearing reasons to subscribe. Each card is a feature the
// user gets exclusively here, with the contrast against alternatives
// (Sora, Veo direct, Runway, Kling) implied not stated.
// ============================================================================
function WhyFaceless() {
  const items = [
    {
      icon: Eye,
      title: "Free script preview",
      ar: "اقرأ القصة قبل أن تدفع",
      body: "Write a one-line premise. We write the full Arabic script — for free. You only pay if you decide to render the video.",
      badge: "No surprise bills",
    },
    {
      icon: RotateCcw,
      title: "Per-clip reroll",
      ar: "أعد توليد لقطة واحدة",
      body: "One clip looks wrong? Reroll just that clip. Pay for one, not all five. Most tools force a full restart.",
      badge: "Pay for what works",
    },
    {
      icon: ShieldCheck,
      title: "Refund on failure",
      ar: "استرداد تلقائي",
      body: "If a render fails partway, every credit charged is automatically returned. You never pay for video you didn't receive.",
      badge: "Money-back guarantee",
    },
    {
      icon: Users,
      title: "Locked characters across clips",
      ar: "نفس الشخصية في كل لقطة",
      body: "Same face, same voice, same outfit — clip after clip. Built on a reference image so identity persists where generic models drift.",
      badge: "Consistent cast",
    },
    {
      icon: Sparkles,
      title: "Plus a full song studio",
      ar: "وأيضًا استوديو أغاني كامل",
      body: "Same account, second mode: theme → full Arabic song with Suno V5 vocals, lyric-aware cover art, and a sharable music-video page with karaoke-style lyric reveal.",
      badge: "Two modes, one studio",
    },
  ];
  return (
    <section id="why" className="relative py-24 px-5 sm:px-8 border-t border-white/[0.05]">
      <div className="max-w-7xl mx-auto">
        <SectionEyebrow text="WHY US" />
        <SectionTitle en="Built for Arabic creators." ar="مصنوع لصُنّاع المحتوى العربي" />
        <p className="mt-4 text-muted max-w-2xl">
          What the big AI tools won't give you: cost transparency, recovery
          from failure, Arabic as a first-class citizen — and a music studio
          in the same account.
        </p>
        <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {items.map((it, i) => (
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 32, filter: "blur(8px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{
                duration: 0.7,
                delay: i * 0.08,
                ease: [0.16, 1, 0.3, 1],
              }}
              className="relative bg-gradient-to-br from-accent/[0.05] to-transparent border border-accent/20 rounded-2xl p-7 hover:border-accent/40 transition-colors"
            >
              <span className="absolute top-5 right-5 text-[10px] font-bold text-accent tracking-[0.15em] uppercase px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20">
                {it.badge}
              </span>
              <div className="w-11 h-11 rounded-xl bg-accent/10 border border-accent/25 flex items-center justify-center mb-5">
                <it.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="text-xl font-semibold mb-1 tracking-tight">
                {it.title}
              </h3>
              <div
                className="text-[13px] text-ink/75 mb-3 font-arabic"
                dir="rtl"
                lang="ar"
              >
                {it.ar}
              </div>
              <p className="text-[14px] text-ink/85 leading-relaxed">
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
// FEATURES — the broader set (script writer, cinematic render, dialects,
// PDF). WhyFaceless above carries the differentiation argument; this
// section just enumerates what you actually get.
// ============================================================================
function Features() {
  const items = [
    { icon: Wand2,     title: "AI script writer",   body: "One sentence becomes a full Arabic script. Dialogue, characters, shot directions." },
    { icon: Film,      title: "Cinematic video",    body: "Each beat becomes a clip. Stitched with music and captions. 9:16, ready to share." },
    { icon: Languages, title: "6 Arabic dialects",  body: "MSA, Syrian, Egyptian, Khaliji, Maghrebi, Iraqi. Real dialect voice — not translation." },
    { icon: FileText,  title: "Free script PDF",    body: "Export the director's script even without rendering. Cover, cast, beats — yours to keep." },
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
              initial={{ opacity: 0, y: 32, filter: "blur(8px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{
                duration: 0.7,
                delay: i * 0.1,
                ease: [0.16, 1, 0.3, 1],
              }}
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
              initial={{ opacity: 0, y: 36, filter: "blur(8px)", scale: 0.96 }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)", scale: 1 }}
              viewport={{ once: true, margin: "-30px" }}
              transition={{
                duration: 0.8,
                delay: i * 0.08,
                ease: [0.16, 1, 0.3, 1],
              }}
              className="group relative aspect-[4/5] rounded-2xl overflow-hidden border border-white/10 hover:border-accent/60 hover:scale-[1.02] hover:shadow-[0_0_60px_rgba(231,181,60,0.18)] transition-all duration-300"
            >
              <LazyVideo
                src={mp4(t.vid)}
                className="absolute inset-0 w-full h-full"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent" />
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                   style={{ background: "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(231,181,60,0.18), transparent 60%)" }} />
              <div className="absolute inset-0 p-5 flex flex-col justify-end">
                <div className="text-[10px] font-medium text-white/85 tracking-[0.18em] uppercase mb-1">
                  {t.en}
                </div>
                <div
                  className="text-xl sm:text-2xl font-semibold text-white tracking-tight font-arabic mb-1"
                  dir="rtl"
                  lang="ar"
                >
                  {t.ar}
                </div>
                <p className="text-[11px] text-white/85 leading-snug line-clamp-2">
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
    {
      name: "Silver", price: "$9", credits: 12, blurb: "For trying ideas",
      perks: [
        "12 video clips / month",
        "Free unlimited script previews",
        "Per-clip reroll (no full restart)",
        "Refund on failed renders",
        "All 6 dialects + templates",
      ],
    },
    {
      name: "Gold", price: "$29", credits: 60, blurb: "For weekly drops",
      recommended: true,
      perks: [
        "60 video clips / month",
        "Priority rendering queue",
        "Free unlimited script previews",
        "Per-clip reroll (no full restart)",
        "Refund on failed renders",
        "All 6 dialects + templates",
      ],
    },
    {
      name: "Platinum", price: "$79", credits: 200, blurb: "For daily output",
      perks: [
        "200 video clips / month",
        "Priority rendering queue",
        "Free unlimited script previews",
        "Per-clip reroll (no full restart)",
        "Refund on failed renders",
        "All 6 dialects + templates",
      ],
    },
  ];
  return (
    <section id="pricing" className="relative py-24 px-5 sm:px-8 border-t border-white/[0.05]">
      <div className="max-w-5xl mx-auto">
        <SectionEyebrow text="PRICING" />
        <SectionTitle en="Subscribe once. Render every month." ar="اشترك مرة. ارند كل شهر" />
        <p className="mt-4 text-muted max-w-2xl">
          1 credit = 1 video clip. Pause or change tier any time.
          <span className="text-ink/85"> Every plan includes free unlimited script previews and automatic refund if a render fails — you only pay for video that actually delivers.</span>
        </p>
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-3">
          {tiers.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 36, filter: "blur(8px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{
                duration: 0.8,
                delay: i * 0.12,
                ease: [0.16, 1, 0.3, 1],
              }}
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
      <Aurora intensity={0.35} />
      <div className="relative max-w-3xl mx-auto text-center">
        <div className="inline-flex justify-center mb-7">
          <SparkleLogo size={56} />
        </div>
        <h2 className="text-4xl sm:text-6xl font-semibold tracking-[-0.035em] mb-5">
          Your first draft is free.
        </h2>
        <p className="text-base sm:text-lg text-muted max-w-md mx-auto mb-9">
          A short video or an Arabic song — write one line, we do the rest.
          Pay only when you generate.
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
            Faceless Lab · faceless-lab.com
          </span>
        </div>
        <div className="sm:ml-auto flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-[13px] text-muted">
          <a href="/pricing" className="hover:text-ink transition-colors">Pricing</a>
          <a href="/about" className="hover:text-ink transition-colors">About</a>
          <a href="/press" className="hover:text-ink transition-colors">Press</a>
          <a href="/terms" className="hover:text-ink transition-colors">Terms</a>
          <a href="/privacy" className="hover:text-ink transition-colors">Privacy</a>
          <a href="/refund" className="hover:text-ink transition-colors">Refunds</a>
          <a href="/contact" className="hover:text-ink transition-colors">Contact</a>
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
      initial={{ opacity: 0, y: 24, filter: "blur(12px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
      className="text-3xl sm:text-5xl lg:text-6xl font-semibold tracking-[-0.03em] leading-tight"
    >
      {en}
      <span
        // text-muted at full opacity (#B4BAC4) clears 4.5:1 against bg.
        // The previous /60 modifier dropped it below 3:1.
        className="ml-3 text-muted text-xl sm:text-2xl font-normal font-arabic"
        dir="rtl"
        lang="ar"
      >
        {ar}
      </span>
    </motion.h2>
  );
}
