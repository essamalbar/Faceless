"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform, type MotionValue } from "framer-motion";
import { Sparkles, FileText, Film } from "lucide-react";
import { LazyVideo } from "./lazy-video";

/**
 * ScrollPipeline — Leonardo.ai-style sticky horizontal-scroll, redesigned
 * for cinematic feel. Each stage is a full-bleed visual (a real video
 * clip or a frame-level mockup) with overlay text — like three movie
 * stills the user pans through. Letterbox bars slide in/out at section
 * boundaries. Stages cross-fade rather than hard-cut so the whole
 * thing feels like one continuous take.
 */
export function ScrollPipeline() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"],
  });

  // Track translateX with dwell windows. Smoother than a pure linear
  // map — each stage holds at centre for a real reading window, then
  // glides into the next with eased momentum.
  const x = useTransform(
    scrollYProgress,
    [0, 0.18, 0.4, 0.6, 0.82, 1],
    ["0%", "0%", "-33.33%", "-33.33%", "-66.67%", "-66.67%"],
  );

  // Cross-fade opacities — neighbour stages keep some presence during
  // transitions so the eye never sees a hard cut. Each stage sits at
  // 1 during its dwell, fades to 0.55 mid-transition, never below.
  const s1Opacity = useTransform(scrollYProgress, [0, 0.18, 0.35], [1, 1, 0.55]);
  const s2Opacity = useTransform(
    scrollYProgress,
    [0.2, 0.4, 0.6, 0.8],
    [0.55, 1, 1, 0.55],
  );
  const s3Opacity = useTransform(scrollYProgress, [0.65, 0.82, 1], [0.55, 1, 1]);

  // Letterbox bars — slide in as the section pins, retract as it leaves.
  // Gives the whole sequence a cinema-screen frame around it.
  const letterboxHeight = useTransform(
    scrollYProgress,
    [0, 0.08, 0.92, 1],
    ["0%", "8%", "8%", "0%"],
  );

  // Section-enter mask — soft fade-in for the entire stack so the
  // pipeline emerges rather than snaps into place.
  const sectionOpacity = useTransform(
    scrollYProgress,
    [0, 0.04, 0.96, 1],
    [0.6, 1, 1, 0.6],
  );

  // Progress bar at the very top of the pinned pane
  const progressWidth = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  return (
    <section
      ref={ref}
      className="relative bg-bg"
      style={{ height: "400vh" }}
    >
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        {/* Top letterbox bar */}
        <motion.div
          className="absolute top-0 left-0 right-0 bg-black z-30 pointer-events-none"
          style={{ height: letterboxHeight }}
        />
        {/* Bottom letterbox bar */}
        <motion.div
          className="absolute bottom-0 left-0 right-0 bg-black z-30 pointer-events-none"
          style={{ height: letterboxHeight }}
        />

        {/* Live progress bar — anchored just under the top letterbox */}
        <motion.div
          className="absolute top-0 left-0 h-[2px] bg-accent z-40 pointer-events-none"
          style={{ width: progressWidth }}
        />

        {/* Eyebrow + heading — floats over the cinematic strip, top-left */}
        <div className="absolute top-0 left-0 right-0 z-20 pt-[10vh] sm:pt-[12vh] px-5 sm:px-8 pointer-events-none">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-px bg-accent" />
              <span className="text-[10px] font-bold text-accent tracking-[0.22em]">
                HOW IT WORKS
              </span>
            </div>
            <div className="flex items-baseline gap-3 flex-wrap">
              <h2 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-[-0.03em] leading-tight text-white drop-shadow-lg">
                Watch it build.
              </h2>
              <span
                className="text-base sm:text-lg text-white/70 font-arabic"
                dir="rtl"
              >
                شاهدها تُبنى
              </span>
            </div>
          </div>
        </div>

        {/* Horizontal cinematic strip */}
        <motion.div
          style={{ x, opacity: sectionOpacity }}
          className="absolute inset-0 flex"
        >
          <CinematicStage
            opacity={s1Opacity}
            kicker="STEP 01 · WRITE"
            title="One line is enough."
            ar="جملة واحدة تكفي"
            visual={<Stage1Visual />}
          />
          <CinematicStage
            opacity={s2Opacity}
            kicker="STEP 02 · SCRIPT"
            title="AI writes your story."
            ar="الذكاء الاصطناعي يكتب قصتك"
            visual={<Stage2Visual />}
          />
          <CinematicStage
            opacity={s3Opacity}
            kicker="STEP 03 · RENDER"
            title="Cinematic short, delivered."
            ar="فيلم قصير سينمائي"
            visual={<Stage3Visual />}
          />
        </motion.div>

        {/* Stage progress dots — anchored above the bottom letterbox */}
        <div className="absolute left-0 right-0 z-20 pb-[10vh] sm:pb-[12vh] bottom-0 flex justify-center pointer-events-none">
          <ProgressDots scrollYProgress={scrollYProgress} />
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// CINEMATIC STAGE — full-bleed visual + bottom-aligned overlay text
// ============================================================================
function CinematicStage({
  opacity,
  kicker,
  title,
  ar,
  visual,
}: {
  opacity: MotionValue<number>;
  kicker: string;
  title: string;
  ar: string;
  visual: React.ReactNode;
}) {
  return (
    <motion.div
      style={{ opacity }}
      className="w-screen h-full flex-shrink-0 relative overflow-hidden"
    >
      {/* Full-bleed background visual (film still) */}
      <div className="absolute inset-0">{visual}</div>

      {/* Soft cinematic vignette: dark at top + bottom for legibility */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/85 pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-r from-black/55 via-transparent to-transparent pointer-events-none" />

      {/* Stage text overlay — bottom-left */}
      <div className="absolute inset-x-0 bottom-0 z-10 pb-[16vh] sm:pb-[18vh] px-5 sm:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-[11px] font-bold text-accent tracking-[0.22em] mb-3">
            {kicker}
          </div>
          <h3 className="text-3xl sm:text-5xl lg:text-7xl font-semibold tracking-[-0.035em] leading-[1.02] text-white drop-shadow-2xl max-w-3xl mb-3">
            {title}
          </h3>
          <p
            className="text-base sm:text-xl text-white/75 font-arabic"
            dir="rtl"
          >
            {ar}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

// ============================================================================
// PROGRESS DOTS
// ============================================================================
function ProgressDots({
  scrollYProgress,
}: {
  scrollYProgress: ReturnType<typeof useScroll>["scrollYProgress"];
}) {
  const stageIdx: MotionValue<number> = useTransform(
    scrollYProgress,
    (p): number => {
      if (p < 0.29) return 0;
      if (p < 0.71) return 1;
      return 2;
    },
  );
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
  const w = useTransform(activeIdx, (a) => (a === index ? 32 : 8));
  const bg = useTransform(activeIdx, (a) =>
    a === index ? "#E7B53C" : "rgba(255,255,255,0.25)",
  );
  return (
    <motion.div
      style={{ width: w, backgroundColor: bg }}
      className="h-2 rounded-full"
    />
  );
}

// ============================================================================
// PER-STAGE VISUALS — each is full-bleed and looks like a film still
// ============================================================================

// Stage 1 — atmospheric dark room with floating prompt card centered
function Stage1Visual() {
  return (
    <div className="absolute inset-0">
      {/* Cinematic background: atmospheric Mixkit clip */}
      <LazyVideo
        src="https://assets.mixkit.co/videos/9582/9582-720.mp4"
        className="absolute inset-0 w-full h-full"
        rootMargin="400px"
      />
      <div className="absolute inset-0 bg-black/45" />
      {/* Floating prompt frame, centered with a soft glow */}
      <div className="absolute inset-0 flex items-center justify-center px-5 pointer-events-none">
        <div className="relative max-w-md w-full">
          <div
            className="absolute inset-0 rounded-2xl blur-2xl opacity-50"
            style={{ background: "radial-gradient(circle at 50% 50%, rgba(231,181,60,0.5), transparent 70%)" }}
          />
          <div className="relative rounded-2xl border border-white/20 bg-black/60 backdrop-blur-xl shadow-2xl shadow-black/60 overflow-hidden">
            <div className="px-5 pt-5 pb-3 min-h-[120px]">
              <div className="text-[10px] text-white/50 tracking-[0.15em] mb-3">
                PREMISE
              </div>
              <div className="text-xl font-arabic text-white leading-relaxed" dir="rtl">
                في قرية معزولة عند سفح الجبل،
                <span className="inline-block w-[2px] h-5 bg-accent ml-1 -mb-1 animate-pulse" />
              </div>
            </div>
            <div className="flex items-center justify-between px-3 pb-3 pt-1 border-t border-white/10">
              <span className="text-[10px] text-white/50 px-2 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-accent" /> One line is enough
              </span>
              <div className="bg-accent text-bg font-semibold text-[12px] px-3 py-1.5 rounded-lg">
                Generate →
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Stage 2 — script.json reveal with cinematic backdrop
function Stage2Visual() {
  const beats = [
    { idx: "01", ch: "الراوي", line: "كان البئر يحرس أسرار الماضي." },
    { idx: "02", ch: "حورية",  line: "كل من نظر فيه رأى وجهه." },
    { idx: "03", ch: "خالد",   line: "تراجع، لكن الصوت ناداه." },
    { idx: "04", ch: "الراوي", line: "لم يعد إلى القرية تلك الليلة." },
  ];
  return (
    <div className="absolute inset-0">
      <LazyVideo
        src="https://assets.mixkit.co/videos/30605/30605-720.mp4"
        className="absolute inset-0 w-full h-full"
        rootMargin="400px"
      />
      <div className="absolute inset-0 bg-black/55" />
      <div className="absolute inset-0 flex items-center justify-center px-5 pointer-events-none">
        <div className="relative max-w-md w-full">
          <div
            className="absolute inset-0 rounded-2xl blur-2xl opacity-40"
            style={{ background: "radial-gradient(circle at 50% 50%, rgba(139,92,246,0.5), transparent 70%)" }}
          />
          <div className="relative bg-black/65 backdrop-blur-xl border border-white/20 rounded-2xl overflow-hidden shadow-2xl shadow-black/60">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 bg-white/[0.03]">
              <FileText className="w-3.5 h-3.5 text-accent" />
              <span className="text-[10px] font-mono text-white/60 tracking-wider">
                script.json
              </span>
              <span className="ml-auto text-[10px] font-bold text-accent tracking-wider">
                4 / 4 BEATS
              </span>
            </div>
            <div className="p-4 space-y-2">
              {beats.map((b) => (
                <div key={b.idx} className="flex items-start gap-3 p-2.5 rounded-lg bg-white/[0.04] border border-white/5">
                  <div className="text-accent font-bold text-xs tracking-wider w-7 flex-shrink-0">
                    {b.idx}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-white/50 tracking-wider mb-0.5">
                      {b.ch}
                    </div>
                    <div className="text-sm text-white font-arabic leading-snug truncate" dir="rtl">
                      {b.line}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Stage 3 — final rendered film
function Stage3Visual() {
  return (
    <div className="absolute inset-0">
      <LazyVideo
        src="https://assets.mixkit.co/videos/45584/45584-720.mp4"
        className="absolute inset-0 w-full h-full"
        rootMargin="400px"
      />
      <div className="absolute inset-0 bg-black/35" />
      <div className="absolute inset-0 flex items-center justify-center px-5 pointer-events-none">
        <div className="relative w-[60vw] sm:w-[36vw] lg:w-[24vw] max-w-[260px]">
          <div
            className="absolute -inset-3 rounded-2xl blur-2xl opacity-60"
            style={{ background: "radial-gradient(circle at 50% 50%, rgba(231,181,60,0.5), transparent 70%)" }}
          />
          <div className="relative aspect-[9/16] rounded-2xl overflow-hidden border-2 border-accent/50 bg-black/55 shadow-2xl shadow-black/70">
            <LazyVideo
              src="https://assets.mixkit.co/videos/46702/46702-720.mp4"
              className="absolute inset-0 w-full h-full"
              rootMargin="400px"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
            <div className="absolute top-3 left-3 flex items-center gap-2 px-2.5 py-1 rounded-full bg-black/70 backdrop-blur border border-accent/40">
              <Film className="w-3 h-3 text-accent" />
              <span className="text-[10px] font-bold text-accent tracking-wider">RENDERED</span>
            </div>
            <div className="absolute inset-x-0 bottom-0 p-4">
              <div className="text-[10px] text-white/70 tracking-[0.15em] uppercase mb-1">
                FINAL · 32s · 9:16
              </div>
              <div className="text-lg font-bold text-white font-arabic" dir="rtl">
                البئر المهجور
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
