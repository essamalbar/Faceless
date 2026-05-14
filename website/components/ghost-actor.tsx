"use client";

/**
 * GhostActor — a big walking shadow figure that traverses its parent
 * horizontally. The figure is built from grouped SVG primitives (head,
 * torso, two arms, two legs) so individual limbs can swing on their
 * own CSS keyframe timelines, producing a proper walk cycle instead
 * of a sliding silhouette.
 *
 * Everything is GPU-only transforms; no canvas, no JS scheduling. Runs
 * 60fps even on mid-range phones.
 */
export function GhostActor({
  direction = "ltr",
  bottom = "0%",
  height = 380,
  opacity = 0.55,
  duration = 18,
  delay = 0,
}: {
  /** Direction of travel across the parent */
  direction?: "ltr" | "rtl";
  /** Distance from the parent's bottom (CSS value). Figure stands on
      this line so the feet appear grounded. */
  bottom?: string;
  /** Figure height in pixels. 380 reads as roughly human-scale next to
      the hero's H1; bump for the cinematic pass. */
  height?: number;
  /** Final shadow opacity */
  opacity?: number;
  /** Seconds for one full traversal */
  duration?: number;
  /** Seconds to wait before the first traversal */
  delay?: number;
}) {
  const id = `g${direction}-${duration}-${delay}`.replace(/\./g, "");
  return (
    <div
      className="pointer-events-none absolute z-[1]"
      style={{
        bottom,
        height,
        width: height * 0.45,
        opacity,
        animationName: `drift-${id}`,
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
        animationIterationCount: "infinite",
        animationTimingFunction: "linear",
        // Drop a soft shadow under the feet so the figure looks grounded
        filter: "drop-shadow(0 12px 24px rgba(0,0,0,0.6))",
      }}
    >
      {/* Inner bob — slight up-down with each step */}
      <div
        className="w-full h-full"
        style={{
          animationName: `bob-${id}`,
          animationDuration: "0.9s",
          animationIterationCount: "infinite",
          animationTimingFunction: "ease-in-out",
        }}
      >
        <svg
          viewBox="0 0 100 220"
          className="w-full h-full"
          // Mirror the figure horizontally for right-to-left travel so
          // the silhouette appears to face its direction of motion
          style={{ transform: direction === "rtl" ? "scaleX(-1)" : undefined }}
        >
          {/* Head */}
          <circle cx="50" cy="22" r="12" fill="#000" />
          {/* Neck */}
          <rect x="46" y="32" width="8" height="6" fill="#000" />

          {/* Torso — narrower at waist for human silhouette */}
          <path
            d="M36,40 Q50,38 64,40 L60,118 Q50,120 40,118 Z"
            fill="#000"
          />

          {/* Left arm — swings forward+back */}
          <g
            style={{
              transformOrigin: "44px 44px",
              animationName: `arm-l-${id}`,
              animationDuration: "0.9s",
              animationIterationCount: "infinite",
              animationTimingFunction: "ease-in-out",
            }}
          >
            <rect x="30" y="44" width="8" height="70" rx="4" fill="#000" />
            {/* Hand */}
            <circle cx="34" cy="116" r="5" fill="#000" />
          </g>

          {/* Right arm — opposite phase */}
          <g
            style={{
              transformOrigin: "56px 44px",
              animationName: `arm-r-${id}`,
              animationDuration: "0.9s",
              animationIterationCount: "infinite",
              animationTimingFunction: "ease-in-out",
            }}
          >
            <rect x="62" y="44" width="8" height="70" rx="4" fill="#000" />
            <circle cx="66" cy="116" r="5" fill="#000" />
          </g>

          {/* Left leg */}
          <g
            style={{
              transformOrigin: "44px 120px",
              animationName: `leg-l-${id}`,
              animationDuration: "0.9s",
              animationIterationCount: "infinite",
              animationTimingFunction: "ease-in-out",
            }}
          >
            <rect x="40" y="118" width="10" height="80" rx="4" fill="#000" />
            {/* Foot */}
            <ellipse cx="45" cy="206" rx="9" ry="5" fill="#000" />
          </g>

          {/* Right leg — opposite phase */}
          <g
            style={{
              transformOrigin: "56px 120px",
              animationName: `leg-r-${id}`,
              animationDuration: "0.9s",
              animationIterationCount: "infinite",
              animationTimingFunction: "ease-in-out",
            }}
          >
            <rect x="50" y="118" width="10" height="80" rx="4" fill="#000" />
            <ellipse cx="55" cy="206" rx="9" ry="5" fill="#000" />
          </g>
        </svg>
      </div>

      <style jsx>{`
        @keyframes drift-${id} {
          0% {
            transform: translateX(${direction === "ltr" ? "-25vw" : "calc(100vw + 25vw)"});
          }
          100% {
            transform: translateX(${direction === "ltr" ? "calc(100vw + 25vw)" : "-25vw"});
          }
        }
        @keyframes bob-${id} {
          0%, 100% { transform: translateY(0); }
          50%      { transform: translateY(-6px); }
        }
        /* Limb swings — legs and arms move in opposite phase, like a
           real walk cycle. */
        @keyframes leg-l-${id} {
          0%, 100% { transform: rotate(-22deg); }
          50%      { transform: rotate(22deg); }
        }
        @keyframes leg-r-${id} {
          0%, 100% { transform: rotate(22deg); }
          50%      { transform: rotate(-22deg); }
        }
        @keyframes arm-l-${id} {
          0%, 100% { transform: rotate(20deg); }
          50%      { transform: rotate(-20deg); }
        }
        @keyframes arm-r-${id} {
          0%, 100% { transform: rotate(-20deg); }
          50%      { transform: rotate(20deg); }
        }
      `}</style>
    </div>
  );
}
