"use client";

/**
 * Aurora — flowing gradient mesh behind a section. Three large blurred
 * radial blobs in champagne / deep teal, each drifting and scaling on
 * independent timers. Obsidian & Champagne palette only — amber/champagne
 * and deep teal, nothing cooler or more saturated. GPU-only transforms;
 * no JS. Animation durations are killed by the global
 * `prefers-reduced-motion` rule in globals.css.
 */
export function Aurora({
  className = "",
  intensity = 0.55,
}: {
  className?: string;
  intensity?: number;
}) {
  return (
    <div
      className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}
      style={{ opacity: intensity }}
      aria-hidden="true"
    >
      <div
        className="absolute -top-[10%] left-[10%] w-[55vw] h-[55vw] max-w-[700px] max-h-[700px] rounded-full blur-[120px] bg-accent mix-blend-screen"
        style={{ animation: "aurora-1 22s ease-in-out infinite" }}
      />
      <div
        className="absolute top-[20%] right-[5%] w-[50vw] h-[50vw] max-w-[650px] max-h-[650px] rounded-full blur-[140px] bg-[#2E7A6E] mix-blend-screen"
        style={{ animation: "aurora-2 28s ease-in-out infinite" }}
      />
      <div
        className="absolute bottom-[10%] left-[35%] w-[60vw] h-[60vw] max-w-[750px] max-h-[750px] rounded-full blur-[160px] bg-accentDeep mix-blend-screen"
        style={{ animation: "aurora-3 34s ease-in-out infinite" }}
      />
      <style jsx>{`
        @keyframes aurora-1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%      { transform: translate(60px, -40px) scale(1.15); }
          66%      { transform: translate(-30px, 30px) scale(0.95); }
        }
        @keyframes aurora-2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%      { transform: translate(-70px, 50px) scale(1.1); }
          66%      { transform: translate(40px, -30px) scale(1.2); }
        }
        @keyframes aurora-3 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50%      { transform: translate(50px, -60px) scale(1.15); }
        }
      `}</style>
    </div>
  );
}
