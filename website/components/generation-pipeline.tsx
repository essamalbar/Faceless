"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, AnimatePresence } from "framer-motion";
import { Sparkles, Check, Film, Type, Layers } from "lucide-react";

/**
 * GenerationPipeline — the "see it generate in real time" section.
 *
 * Four staged sub-animations that play in sequence the first time the
 * section enters the viewport:
 *
 *   1. Premise types itself into a console
 *   2. Script beats fade in one by one beside the console
 *   3. Clip cards render with staggered progress bars
 *   4. Final video card materialises with a play button
 *
 * Stays in the final state after playing. Pure React + framer-motion;
 * no external animation libraries.
 */

const PREMISE = "في قرية معزولة عند سفح الجبل،";

// Each beat carries the Mixkit video ID that "plays" in the matching
// ClipCard once that clip finishes rendering. Closes the loop between
// script generation and the visual outcome: visitors see a real human
// in motion at the end of each pipeline lane.
const BEATS = [
  { idx: "01", name: "الراوي", line: "كان البئر القديم يحرس أسرار الماضي.", vid: 9582 },
  { idx: "02", name: "حورية",  line: "كل من نظر فيه رأى وجهه الذي لم يصل.",  vid: 1114 },
  { idx: "03", name: "خالد",   line: "تراجع، لكن صوته ناداه من قاع الماء.",  vid: 1038 },
  { idx: "04", name: "الراوي", line: "لم يعد إلى القرية ذلك المساء.",       vid: 1116 },
];

export function GenerationPipeline() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  const [stage, setStage] = useState(0);

  // Sequence: typing → beats appear → clips render → final pops
  useEffect(() => {
    if (!inView) return;
    const timers = [
      setTimeout(() => setStage(1), 400),    // start typing
      setTimeout(() => setStage(2), 3700),   // beats appear
      setTimeout(() => setStage(3), 7000),   // clips render
      setTimeout(() => setStage(4), 12500),  // final video
    ];
    return () => timers.forEach(clearTimeout);
  }, [inView]);

  return (
    <section
      ref={ref}
      className="relative py-32 px-5 sm:px-8 overflow-hidden bg-surface/10"
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 30%, rgba(231,181,60,0.12), transparent 70%)",
        }}
      />

      <div className="relative max-w-7xl mx-auto">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-px bg-accent" />
          <span className="text-[11px] font-bold text-accent tracking-[0.2em]">
            GENERATION IN ACTION
          </span>
        </div>
        <div className="flex items-baseline gap-3 flex-wrap mb-4">
          <h2 className="text-4xl sm:text-6xl font-extrabold tracking-[-0.03em]">
            Watch it build.
          </h2>
          <span
            className="text-xl sm:text-2xl text-muted/70 font-arabic tracking-tight"
            dir="rtl"
          >
            شاهد عملية الإنشاء
          </span>
        </div>
        <p className="text-muted max-w-2xl mb-16">
          A one-line premise becomes a full Arabic short. Here's the pipeline,
          play-by-play.
        </p>

        {/* Stage indicator bar */}
        <StageIndicator stage={stage} />

        {/* Two-column staged view */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-12">
          <div className="lg:col-span-5">
            <PremiseConsole active={stage >= 1} />
          </div>
          <div className="lg:col-span-7">
            <BeatsList stage={stage} />
          </div>
        </div>

        {/* Clip renderer */}
        <div className="mt-6">
          <ClipRenderer stage={stage} />
        </div>

        {/* Final stitch */}
        <div className="mt-6">
          <FinalStitch active={stage >= 4} />
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// STAGE INDICATOR
// ============================================================================
function StageIndicator({ stage }: { stage: number }) {
  const items = [
    { icon: Type, label: "Premise" },
    { icon: Layers, label: "Script" },
    { icon: Film, label: "Clips" },
    { icon: Check, label: "Final" },
  ];
  return (
    <div className="grid grid-cols-4 gap-2 sm:gap-4">
      {items.map((it, i) => {
        const active = stage > i;
        const current = stage === i + 1;
        return (
          <div key={it.label} className="relative">
            <div
              className={`relative bg-surface/60 backdrop-blur-sm border rounded-xl px-4 py-3 transition-all ${
                active
                  ? "border-accent/50 bg-accent/10"
                  : current
                    ? "border-accent/80 bg-accent/15 shadow-lg shadow-accent/20"
                    : "border-white/10"
              }`}
            >
              <div className="flex items-center gap-2">
                <div
                  className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold transition-colors ${
                    active
                      ? "bg-accent text-bg"
                      : "bg-white/5 text-muted"
                  }`}
                >
                  {active ? <Check className="w-3 h-3" /> : i + 1}
                </div>
                <it.icon className={`w-3.5 h-3.5 ${active ? "text-accent" : "text-muted"}`} />
                <span
                  className={`text-xs font-semibold tracking-wide hidden sm:inline ${
                    active ? "text-ink" : "text-muted"
                  }`}
                >
                  {it.label}
                </span>
              </div>
              {/* Progress pulse on the current stage */}
              {current && (
                <motion.div
                  className="absolute inset-0 rounded-xl border border-accent pointer-events-none"
                  animate={{ opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// STAGE 1 — PREMISE CONSOLE
// ============================================================================
function PremiseConsole({ active }: { active: boolean }) {
  const [chars, setChars] = useState(0);
  useEffect(() => {
    if (!active) return;
    let i = 0;
    const id = setInterval(() => {
      i++;
      setChars(i);
      if (i >= PREMISE.length) clearInterval(id);
    }, 80);
    return () => clearInterval(id);
  }, [active]);

  return (
    <div className="bg-bg/70 border border-white/10 rounded-2xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 bg-white/[0.02]">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
        <span className="ml-auto text-[10px] font-mono text-muted tracking-wider">
          premise.txt
        </span>
      </div>
      <div className="p-6 min-h-[200px]">
        <div className="text-[10px] text-muted/70 tracking-[0.2em] mb-3">
          INPUT
        </div>
        <div
          className="text-2xl sm:text-3xl font-arabic text-ink leading-relaxed"
          dir="rtl"
        >
          {active ? PREMISE.slice(0, chars) : ""}
          <span
            className={`inline-block w-[3px] h-7 bg-accent ml-1 -mb-1 ${active ? "animate-pulse" : "opacity-0"}`}
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// STAGE 2 — BEATS LIST
// ============================================================================
function BeatsList({ stage }: { stage: number }) {
  return (
    <div className="bg-bg/70 border border-white/10 rounded-2xl overflow-hidden h-full">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 bg-white/[0.02]">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        <span className="text-[10px] font-mono text-muted tracking-wider">
          script.json
        </span>
        {stage >= 2 && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="ml-auto text-[10px] font-bold text-accent tracking-wider"
          >
            {Math.min(stage >= 3 ? 4 : stage * 2, 4)} / 4 BEATS
          </motion.span>
        )}
      </div>
      <div className="p-5 space-y-2.5">
        <AnimatePresence>
          {BEATS.map((b, i) => {
            const visible = stage >= 2 && (stage >= 3 || i < stage * 2);
            if (!visible) return null;
            return (
              <motion.div
                key={b.idx}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, delay: i * 0.18 }}
                className="flex items-start gap-3 p-3 rounded-lg bg-surface/40 border border-white/5"
              >
                <div className="text-accent font-bold text-xs tracking-wider w-7 flex-shrink-0">
                  {b.idx}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-muted tracking-wider mb-0.5">
                    {b.name}
                  </div>
                  <div
                    className="text-sm text-ink font-arabic leading-snug truncate"
                    dir="rtl"
                  >
                    {b.line}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {/* Placeholder rows while waiting */}
        {stage < 2 &&
          [0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-3 rounded-lg bg-surface/20 border border-white/5"
            >
              <div className="w-5 h-3 rounded bg-white/5" />
              <div className="flex-1 space-y-1.5">
                <div className="h-1.5 w-12 rounded bg-white/5" />
                <div className="h-2.5 rounded bg-white/5" style={{ width: `${85 - i * 8}%` }} />
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}

// ============================================================================
// STAGE 3 — CLIP RENDERER
// ============================================================================
function ClipRenderer({ stage }: { stage: number }) {
  const active = stage >= 3;
  // Each clip fills at a different speed for organic feel
  const speeds = [2200, 2600, 3000, 3400];
  return (
    <div className="bg-bg/70 border border-white/10 rounded-2xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 bg-white/[0.02]">
        <Film className="w-3.5 h-3.5 text-accent" />
        <span className="text-[10px] font-mono text-muted tracking-wider">
          rendering clips
        </span>
        {active && (
          <span className="ml-auto text-[10px] font-bold text-accent tracking-wider">
            {stage >= 4 ? "ALL CLIPS RENDERED" : "RENDERING…"}
          </span>
        )}
      </div>
      <div className="p-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {BEATS.map((b, i) => (
          <ClipCard
            key={b.idx}
            index={i + 1}
            active={active}
            speed={speeds[i]}
            videoId={b.vid}
            name={b.name}
          />
        ))}
      </div>
    </div>
  );
}

function ClipCard({
  index,
  active,
  speed,
  videoId,
  name,
}: {
  index: number;
  active: boolean;
  speed: number;
  videoId: number;
  name: string;
}) {
  const [progress, setProgress] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (!active) return;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / speed);
      setProgress(p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, speed]);

  const done = progress >= 1;
  const videoUrl = `https://assets.mixkit.co/videos/${videoId}/${videoId}-720.mp4`;
  // Start the video the moment the card becomes "done" — gives the
  // visceral "AI just rendered a real clip" payoff.
  useEffect(() => {
    if (done) videoRef.current?.play().catch(() => {});
  }, [done]);

  return (
    <div className="relative aspect-[9/16] rounded-xl overflow-hidden border border-white/10 bg-surface/40">
      {/* Background — dark while pending, real human-motion clip when done */}
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(135deg, #1A2238, #0A0E1A)",
        }}
      />
      {/* Real video fades in as progress completes */}
      {active && (
        <motion.div
          className="absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: progress }}
          transition={{ duration: 0.3, ease: "easeOut" }}
        >
          <video
            ref={videoRef}
            src={videoUrl}
            muted
            loop
            playsInline
            preload="auto"
            className="w-full h-full object-cover"
            aria-label={name}
          />
        </motion.div>
      )}
      {/* AI scanlines — only visible while rendering */}
      {active && !done && (
        <motion.div
          className="absolute inset-0 mix-blend-overlay pointer-events-none"
          animate={{ opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity }}
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, rgba(231,181,60,0.3) 0px, transparent 1px, transparent 3px)",
          }}
        />
      )}
      {/* Vignette */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent" />
      <div className="absolute inset-0 p-2 flex flex-col">
        <div className="flex items-start justify-between">
          <div className="text-[9px] font-bold text-white/85 tracking-wider">
            CLIP {String(index).padStart(2, "0")}
          </div>
          {done && (
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="text-[8px] font-bold text-bg bg-accent rounded px-1 py-0.5 tracking-wider"
            >
              READY
            </motion.div>
          )}
        </div>
        <div className="mt-auto">
          {!active && (
            <div className="text-[9px] text-muted/60 tracking-wider">
              WAITING
            </div>
          )}
          {active && !done && (
            <>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] text-white/80 tracking-wider">RENDER</span>
                <span className="text-[9px] text-accent font-bold tabular-nums">
                  {Math.round(progress * 100)}%
                </span>
              </div>
              <div className="h-1 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent to-accent2"
                  style={{ width: `${progress * 100}%`, transition: "width 0.1s linear" }}
                />
              </div>
            </>
          )}
          {done && (
            <div
              className="text-xs text-white font-arabic"
              dir="rtl"
            >
              {name}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// STAGE 4 — FINAL VIDEO
// ============================================================================
function FinalStitch({ active }: { active: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={active ? { opacity: 1, y: 0 } : { opacity: 0.3, y: 20 }}
      transition={{ duration: 0.6 }}
      className="relative rounded-2xl overflow-hidden border border-accent/40 bg-gradient-to-br from-accent/15 to-accent2/15 backdrop-blur-sm"
    >
      <div className="flex items-center gap-4 px-6 py-5">
        <motion.div
          animate={active ? { scale: [1, 1.1, 1], rotate: [0, 5, 0] } : {}}
          transition={{ duration: 2.5, repeat: Infinity }}
          className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center flex-shrink-0 shadow-lg shadow-accent/40"
        >
          <Check className="w-6 h-6 text-bg" />
        </motion.div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            <h3 className="text-xl sm:text-2xl font-bold tracking-tight">
              {active ? "Your video is ready." : "Final stitch…"}
            </h3>
            <span className="text-sm text-muted">
              {active ? "Stitched, scored, captioned." : ""}
            </span>
          </div>
          <div className="mt-1 text-sm text-muted">
            4 clips · 30 seconds · 9:16 vertical · MP4
          </div>
        </div>
        {active && (
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-[10px] text-muted tracking-wider mr-1">DURATION</span>
            <span className="font-bold text-accent text-lg tabular-nums">0:30</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
