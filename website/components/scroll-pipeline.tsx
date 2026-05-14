"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform, type MotionValue } from "framer-motion";
import { Sparkles, FileText, Film } from "lucide-react";
import { LazyVideo } from "./lazy-video";

/**
 * ScrollPipeline — Leonardo.ai-style sticky horizontal-scroll section.
 *
 * The outer wrapper is 3× viewport tall. Inside, a sticky div stays
 * pinned for the entire scroll. A horizontal track inside that holds
 * three full-viewport "stages" — Write, Script, Render — and pans
 * left as the user scrolls down. So scrolling vertically *feels like*
 * stepping through the pipeline horizontally.
 *
 * Progress indicator at the top fills as the user moves through.
 */
export function ScrollPipeline() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"],
  });
  // Horizontal track translates from 0 to -66.67% (two stages worth)
  // so all 3 stages get an equal slice of the scroll budget.
  const x = useTransform(scrollYProgress, [0, 1], ["0%", "-66.67%"]);

  // Per-stage opacity — only the centred stage is at full opacity, the
  // off-screen ones dim. Gives the pinned section a "now playing" feel.
  const s1Opacity = useTransform(scrollYProgress, [0, 0.2, 0.4], [1, 1, 0.4]);
  const s2Opacity = useTransform(scrollYProgress, [0.25, 0.5, 0.75], [0.4, 1, 0.4]);
  const s3Opacity = useTransform(scrollYProgress, [0.6, 0.8, 1], [0.4, 1, 1]);

  // Progress bar at the top of the sticky pane
  const progressWidth = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  return (
    <section
      ref={ref}
      className="relative bg-bg"
      style={{ height: "300vh" }}
    >
      <div className="sticky top-0 h-screen w-full overflow-hidden flex flex-col">
        {/* Section header — sits above the pinned visual */}
        <div className="pt-20 sm:pt-24 pb-8 px-5 sm:px-8">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-px bg-accent" />
              <span className="text-[10px] font-bold text-accent tracking-[0.22em]">
                HOW IT WORKS
              </span>
            </div>
            <div className="flex items-baseline gap-3 flex-wrap mb-4">
              <h2 className="text-3xl sm:text-5xl lg:text-6xl font-semibold tracking-[-0.03em] leading-tight">
                Scroll to see it build.
              </h2>
              <span
                className="text-xl sm:text-2xl text-muted/60 font-normal font-arabic"
                dir="rtl"
              >
                مرر لتراها تُبنى
              </span>
            </div>
            {/* Live progress bar */}
            <div className="h-px bg-white/[0.06] mt-6 overflow-hidden">
              <motion.div className="h-full bg-accent" style={{ width: progressWidth }} />
            </div>
          </div>
        </div>

        {/* Horizontal track — moves left as the page scrolls down */}
        <div className="flex-1 overflow-hidden">
          <motion.div
            style={{ x }}
            className="h-full flex"
          >
            <Stage
              opacity={s1Opacity}
              kicker="STEP 01"
              kickerColor="accent"
              title="Write one line."
              ar="اكتب جملة واحدة"
              body="Type a premise — a fragment, a feeling. The shorter, the better."
              detail="Free · no card · auto-saved"
              visual={<Stage1Visual />}
            />
            <Stage
              opacity={s2Opacity}
              kicker="STEP 02"
              kickerColor="accent"
              title="AI writes your script."
              ar="الذكاء الاصطناعي يكتب لك"
              body="Beats, characters, dialogue, shot directions — generated in seconds. Arabic, voice-locked."
              detail="Free · export as PDF"
              visual={<Stage2Visual />}
            />
            <Stage
              opacity={s3Opacity}
              kicker="STEP 03"
              kickerColor="accent"
              title="Render the video."
              ar="ارند الفيديو"
              body="Each beat becomes a clip. Stitched with music and captions. 9:16, ready to share."
              detail="1 credit per clip"
              visual={<Stage3Visual />}
            />
          </motion.div>
        </div>

        {/* Stage indicator dots */}
        <div className="pb-12 flex justify-center">
          <ProgressDots scrollYProgress={scrollYProgress} />
        </div>
      </div>
    </section>
  );
}

function Stage({
  opacity,
  kicker,
  kickerColor,
  title,
  ar,
  body,
  detail,
  visual,
}: {
  opacity: MotionValue<number>;
  kicker: string;
  kickerColor: string;
  title: string;
  ar: string;
  body: string;
  detail: string;
  visual: React.ReactNode;
}) {
  return (
    <motion.div
      style={{ opacity }}
      className="w-screen h-full flex-shrink-0 px-5 sm:px-8 flex items-center"
    >
      <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        {/* Left — copy */}
        <div>
          <div className={`text-[11px] font-bold text-${kickerColor} tracking-[0.22em] mb-5`}>
            {kicker}
          </div>
          <h3 className="text-4xl sm:text-6xl font-semibold tracking-[-0.035em] leading-[1.05] mb-3">
            {title}
          </h3>
          <p className="text-lg text-muted/80 font-arabic mb-6" dir="rtl">
            {ar}
          </p>
          <p className="text-base sm:text-lg text-ink/80 leading-relaxed max-w-md mb-6">
            {body}
          </p>
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-accent/30 bg-accent/[0.08] text-[12px] font-medium text-accent">
            <Sparkles className="w-3 h-3" />
            {detail}
          </div>
        </div>

        {/* Right — visual */}
        <div className="relative">{visual}</div>
      </div>
    </motion.div>
  );
}

function ProgressDots({
  scrollYProgress,
}: {
  scrollYProgress: ReturnType<typeof useScroll>["scrollYProgress"];
}) {
  // Map scroll progress to active dot index. Explicitly typed as
  // MotionValue<number> so TS doesn't infer the literal union 0|1|2.
  const stageIdx: MotionValue<number> = useTransform(scrollYProgress, (p): number => {
    if (p < 0.33) return 0;
    if (p < 0.66) return 1;
    return 2;
  });
  return (
    <div className="flex items-center gap-2.5">
      {[0, 1, 2].map((i) => (
        <Dot key={i} index={i} activeIdx={stageIdx} />
      ))}
    </div>
  );
}

function Dot({
  index,
  activeIdx,
}: {
  index: number;
  activeIdx: MotionValue<number>;
}) {
  const w = useTransform(activeIdx, (a) => (a === index ? 28 : 8));
  const bg = useTransform(activeIdx, (a) =>
    a === index ? "#E7B53C" : "rgba(255,255,255,0.2)",
  );
  return (
    <motion.div
      style={{ width: w, backgroundColor: bg }}
      className="h-2 rounded-full transition-all"
    />
  );
}

// ============================================================================
// PER-STAGE VISUALS
// ============================================================================
function Stage1Visual() {
  // Mock prompt-input frame to mirror the hero's affordance
  return (
    <div className="relative max-w-md mx-auto">
      <div className="relative rounded-2xl border border-white/15 bg-black/55 backdrop-blur-xl shadow-2xl shadow-black/40 overflow-hidden">
        <div className="px-5 pt-5 pb-3 min-h-[120px]">
          <div className="text-[10px] text-muted/70 tracking-[0.15em] mb-3">PREMISE</div>
          <div className="text-xl font-arabic text-ink leading-relaxed" dir="rtl">
            في قرية معزولة عند سفح الجبل،
            <span className="inline-block w-[2px] h-5 bg-accent ml-1 -mb-1 animate-pulse" />
          </div>
        </div>
        <div className="flex items-center justify-between px-3 pb-3 pt-1 border-t border-white/5">
          <span className="text-[10px] text-muted/70 px-2 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-accent" /> One line is enough
          </span>
          <button className="bg-accent text-bg font-semibold text-[12px] px-3 py-1.5 rounded-lg">
            Generate →
          </button>
        </div>
      </div>
    </div>
  );
}

function Stage2Visual() {
  const beats = [
    { idx: "01", ch: "الراوي", line: "كان البئر يحرس أسرار الماضي." },
    { idx: "02", ch: "حورية",  line: "كل من نظر فيه رأى وجهه." },
    { idx: "03", ch: "خالد",   line: "تراجع، لكن الصوت ناداه." },
    { idx: "04", ch: "الراوي", line: "لم يعد إلى القرية تلك الليلة." },
  ];
  return (
    <div className="relative max-w-md mx-auto bg-black/55 backdrop-blur-xl border border-white/15 rounded-2xl overflow-hidden shadow-2xl shadow-black/40">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 bg-white/[0.02]">
        <FileText className="w-3.5 h-3.5 text-accent" />
        <span className="text-[10px] font-mono text-muted tracking-wider">
          script.json
        </span>
        <span className="ml-auto text-[10px] font-bold text-accent tracking-wider">
          4 / 4 BEATS
        </span>
      </div>
      <div className="p-4 space-y-2">
        {beats.map((b) => (
          <div key={b.idx} className="flex items-start gap-3 p-2.5 rounded-lg bg-surface/40 border border-white/5">
            <div className="text-accent font-bold text-xs tracking-wider w-7 flex-shrink-0">
              {b.idx}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] text-muted tracking-wider mb-0.5">{b.ch}</div>
              <div className="text-sm text-ink font-arabic leading-snug truncate" dir="rtl">
                {b.line}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stage3Visual() {
  return (
    <div className="relative max-w-md mx-auto">
      <div className="relative aspect-[9/16] rounded-2xl overflow-hidden border border-accent/40 bg-black/55 shadow-2xl shadow-black/40">
        <LazyVideo
          src="https://assets.mixkit.co/videos/30605/30605-720.mp4"
          className="absolute inset-0 w-full h-full"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
        <div className="absolute top-3 left-3 flex items-center gap-2 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur border border-accent/40">
          <Film className="w-3 h-3 text-accent" />
          <span className="text-[10px] font-bold text-accent tracking-wider">RENDERED</span>
        </div>
        <div className="absolute inset-x-0 bottom-0 p-4">
          <div className="text-[10px] text-white/70 tracking-[0.15em] uppercase mb-1">
            FINAL · 32 SECONDS · 9:16
          </div>
          <div className="text-lg font-bold text-white font-arabic" dir="rtl">
            البئر المهجور
          </div>
        </div>
      </div>
    </div>
  );
}
