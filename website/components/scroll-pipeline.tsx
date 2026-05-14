"use client";

import { motion } from "framer-motion";
import { Sparkles, FileText, Film } from "lucide-react";
import { LazyVideo } from "./lazy-video";

/**
 * ScrollPipeline — clean vertical timeline. Replaces the previous
 * sticky horizontal-scroll experiment, which felt heavy and over-
 * engineered. This is the Binghatti about-us timeline pattern: a
 * vertical line with milestones, each milestone reveals with a soft
 * fade-up as it scrolls into view. No pinning, no horizontal scroll,
 * no spring physics. Just smooth, professional reveals.
 */

const STEPS = [
  {
    step: "01",
    icon: Sparkles,
    en: "Write a one-line premise",
    ar: "اكتب جملة افتتاحية",
    body:
      "Type a single sentence — a feeling, a setting, a fragment. The shorter, the better.",
    detail: "Free · no card required",
    visual: <Step1Visual />,
  },
  {
    step: "02",
    icon: FileText,
    en: "AI writes the script",
    ar: "الذكاء الاصطناعي يكتب القصة",
    body:
      "Beats, characters, dialogue, and shot directions — generated in seconds. Arabic, voice-locked across the cast.",
    detail: "Free · download the director's PDF",
    visual: <Step2Visual />,
  },
  {
    step: "03",
    icon: Film,
    en: "Render the cinematic short",
    ar: "ارند الفيديو السينمائي",
    body:
      "Each beat becomes a clip. Stitched with music and captions. 9:16 vertical, ready for any feed.",
    detail: "1 credit per clip",
    visual: <Step3Visual />,
  },
];

export function ScrollPipeline() {
  return (
    <section
      id="how"
      className="relative py-28 sm:py-36 px-5 sm:px-8 border-t border-white/[0.05]"
    >
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 24, filter: "blur(10px)" }}
          whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="mb-16 sm:mb-24"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-px bg-accent" />
            <span className="text-[10px] font-bold text-accent tracking-[0.22em]">
              HOW IT WORKS
            </span>
          </div>
          <div className="flex items-baseline gap-3 flex-wrap">
            <h2 className="text-3xl sm:text-5xl lg:text-6xl font-semibold tracking-[-0.03em] leading-tight">
              Three steps. No editing required.
            </h2>
            <span
              className="text-xl sm:text-2xl text-muted/60 font-normal font-arabic"
              dir="rtl"
            >
              ثلاث خطوات بلا مونتاج
            </span>
          </div>
        </motion.div>

        {/* Timeline */}
        <div className="relative">
          {/* Vertical line down the left (mobile) / centre (desktop).
              Subtle gold→fade-out gradient so it doesn't read as a
              hard rail. */}
          <div
            className="absolute top-0 bottom-0 left-[19px] sm:left-1/2 sm:-translate-x-1/2 w-px pointer-events-none"
            style={{
              background:
                "linear-gradient(to bottom, transparent 0%, rgba(231,181,60,0.4) 8%, rgba(255,255,255,0.08) 50%, rgba(231,181,60,0.4) 92%, transparent 100%)",
            }}
          />

          {STEPS.map((s, i) => (
            <TimelineRow key={s.step} entry={s} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}

function TimelineRow({
  entry,
  index,
}: {
  entry: (typeof STEPS)[number];
  index: number;
}) {
  // Alternate sides on desktop — odd entries on the right, even on
  // the left. Mobile stays single-column.
  const onRight = index % 2 === 1;
  return (
    <div className="relative pl-12 sm:pl-0 pb-14 sm:pb-24 last:pb-0">
      {/* Step badge — sits on the timeline rail */}
      <motion.div
        initial={{ opacity: 0, scale: 0.5 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, margin: "-120px" }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        className="absolute top-0 left-0 sm:left-1/2 sm:-translate-x-1/2 w-10 h-10 rounded-full bg-bg border border-accent/50 flex items-center justify-center z-10"
      >
        <div className="w-2.5 h-2.5 rounded-full bg-accent" />
        {/* Soft outer glow */}
        <div
          className="absolute inset-0 rounded-full blur-md opacity-60"
          style={{ background: "rgba(231,181,60,0.4)" }}
        />
      </motion.div>

      {/* Content + visual: on desktop they sit on opposite sides of the
          rail; on mobile they stack to the right of the rail */}
      <div
        className={`sm:grid sm:grid-cols-2 sm:gap-12 lg:gap-20 items-center ${
          onRight ? "sm:flex-row-reverse" : ""
        }`}
      >
        {/* Text column */}
        <motion.div
          initial={{ opacity: 0, y: 28, filter: "blur(8px)" }}
          whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className={`${onRight ? "sm:order-2 sm:text-left" : "sm:text-right"}`}
        >
          <div className="text-[11px] font-bold text-accent tracking-[0.22em] mb-3">
            STEP {entry.step}
          </div>
          <h3 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-[-0.025em] leading-tight mb-2">
            {entry.en}
          </h3>
          <p
            className={`text-base sm:text-lg text-muted/70 font-arabic mb-4 ${
              onRight ? "" : "sm:text-right"
            }`}
            dir="rtl"
          >
            {entry.ar}
          </p>
          <p className="text-[14px] sm:text-[15px] text-ink/80 leading-relaxed max-w-md mb-4 sm:max-w-none sm:inline-block">
            {entry.body}
          </p>
          <div
            className={`flex ${onRight ? "sm:justify-start" : "sm:justify-end"}`}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-accent/25 bg-accent/[0.06] text-[12px] font-medium text-accent">
              <Sparkles className="w-3 h-3" />
              {entry.detail}
            </div>
          </div>
        </motion.div>

        {/* Visual column */}
        <motion.div
          initial={{ opacity: 0, y: 28, filter: "blur(8px)" }}
          whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{
            duration: 0.9,
            delay: 0.15,
            ease: [0.16, 1, 0.3, 1],
          }}
          className={`mt-6 sm:mt-0 ${onRight ? "sm:order-1" : ""}`}
        >
          {entry.visual}
        </motion.div>
      </div>
    </div>
  );
}

// ============================================================================
// PER-STEP VISUALS — minimal, integrated into the timeline rhythm
// ============================================================================
function Step1Visual() {
  return (
    <div className="relative rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-md overflow-hidden shadow-xl shadow-black/30">
      <div className="px-5 pt-5 pb-3 min-h-[120px]">
        <div className="text-[10px] text-muted/70 tracking-[0.15em] mb-3">
          PREMISE
        </div>
        <div
          className="text-xl font-arabic text-ink leading-relaxed"
          dir="rtl"
        >
          في قرية معزولة عند سفح الجبل،
          <span className="inline-block w-[2px] h-5 bg-accent ml-1 -mb-1 animate-pulse" />
        </div>
      </div>
      <div className="flex items-center justify-between px-3 pb-3 pt-1 border-t border-white/5">
        <span className="text-[10px] text-muted/60 px-2 flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-accent" /> One line is enough
        </span>
        <div className="bg-accent text-bg font-semibold text-[12px] px-3 py-1.5 rounded-lg">
          Generate →
        </div>
      </div>
    </div>
  );
}

function Step2Visual() {
  const beats = [
    { idx: "01", ch: "الراوي", line: "كان البئر يحرس أسرار الماضي." },
    { idx: "02", ch: "حورية", line: "كل من نظر فيه رأى وجهه." },
    { idx: "03", ch: "خالد", line: "تراجع، لكن الصوت ناداه." },
    { idx: "04", ch: "الراوي", line: "لم يعد إلى القرية تلك الليلة." },
  ];
  return (
    <div className="relative rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-md overflow-hidden shadow-xl shadow-black/30">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5">
        <FileText className="w-3.5 h-3.5 text-accent" />
        <span className="text-[10px] font-mono text-muted/60 tracking-wider">
          script.json
        </span>
        <span className="ml-auto text-[10px] font-bold text-accent tracking-wider">
          4 / 4 BEATS
        </span>
      </div>
      <div className="p-4 space-y-2">
        {beats.map((b) => (
          <div
            key={b.idx}
            className="flex items-start gap-3 p-2.5 rounded-lg bg-white/[0.03]"
          >
            <div className="text-accent font-bold text-xs tracking-wider w-7 flex-shrink-0">
              {b.idx}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] text-muted/55 tracking-wider mb-0.5">
                {b.ch}
              </div>
              <div
                className="text-sm text-ink font-arabic leading-snug truncate"
                dir="rtl"
              >
                {b.line}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Step3Visual() {
  return (
    <div className="relative aspect-[9/16] max-w-[260px] mx-auto sm:mx-0 rounded-2xl overflow-hidden border border-accent/40 shadow-xl shadow-black/40">
      {/* Mixkit 30995 — fountain/water-source. Closest visual match to
          the mock script's "old well guarding secrets of the past"
          (كان البئر يحرس أسرار الماضي). Reads as the well image the
          AI would render for that beat. */}
      <LazyVideo
        src="https://assets.mixkit.co/videos/30995/30995-720.mp4"
        className="absolute inset-0 w-full h-full"
        rootMargin="300px"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
      <div className="absolute top-3 left-3 flex items-center gap-2 px-2.5 py-1 rounded-full bg-black/55 backdrop-blur border border-accent/40">
        <Film className="w-3 h-3 text-accent" />
        <span className="text-[10px] font-bold text-accent tracking-wider">
          RENDERED
        </span>
      </div>
      <div className="absolute inset-x-0 bottom-0 p-4">
        <div className="text-[10px] text-white/70 tracking-[0.15em] uppercase mb-1">
          FINAL · 32s · 9:16
        </div>
        <div
          className="text-lg font-bold text-white font-arabic"
          dir="rtl"
        >
          البئر المهجور
        </div>
      </div>
    </div>
  );
}
