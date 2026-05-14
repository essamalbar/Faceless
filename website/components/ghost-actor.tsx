"use client";

/**
 * GhostActor — a translucent silhouette of a walking figure that drifts
 * horizontally across its parent section like an apparition. Multiple
 * instances can co-exist in the same parent at different vertical
 * offsets, speeds, and directions to create a haunted-stage feel.
 *
 * The figure is a hand-drawn SVG (no external assets), styled with low
 * opacity and a soft blur so it reads as a ghost rather than a clean
 * icon. CSS keyframes handle the horizontal traversal so the animation
 * is GPU-only — works at 60fps even on phones.
 */
export function GhostActor({
  direction = "ltr",
  top = "50%",
  size = 160,
  opacity = 0.25,
  duration = 22,
  delay = 0,
  color = "#E7B53C",
  bob = 8,
}: {
  /** Direction of drift across the parent */
  direction?: "ltr" | "rtl";
  /** Vertical position inside the parent (CSS top value) */
  top?: string;
  /** Figure height in px */
  size?: number;
  /** Final ghost opacity (0..1) */
  opacity?: number;
  /** Seconds for one full traversal */
  duration?: number;
  /** Seconds to wait before the first traversal */
  delay?: number;
  /** Silhouette fill colour */
  color?: string;
  /** Vertical bob amplitude in px (small = subtle float) */
  bob?: number;
}) {
  const idSuffix = `${direction}-${duration}-${delay}`;
  return (
    <div
      className="ghost-actor pointer-events-none absolute"
      style={{
        top,
        height: size,
        width: size * 0.45,
        opacity,
        animationName: `ghost-drift-${idSuffix}`,
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
        animationIterationCount: "infinite",
        animationTimingFunction: "linear",
        filter: "blur(0.5px)",
      }}
    >
      <div
        className="w-full h-full"
        style={{
          animationName: `ghost-bob-${idSuffix}`,
          animationDuration: "3.5s",
          animationIterationCount: "infinite",
          animationTimingFunction: "ease-in-out",
        }}
      >
        <svg
          viewBox="0 0 100 220"
          className="w-full h-full"
          // Mirror the figure so it appears to face the direction of travel
          style={{ transform: direction === "rtl" ? "scaleX(-1)" : undefined }}
        >
          {/* Soft outer glow so the silhouette reads as luminous mist */}
          <defs>
            <radialGradient id={`g-${idSuffix}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={color} stopOpacity="0.6" />
              <stop offset="60%" stopColor={color} stopOpacity="0.15" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse cx="50" cy="110" rx="55" ry="100" fill={`url(#g-${idSuffix})`} />

          {/* Head */}
          <ellipse cx="50" cy="32" rx="17" ry="20" fill={color} />
          {/* Cloak / body — soft hourglass with flared bottom suggesting
              robes; the shape is intentionally vague so it reads as
              "spectral figure" not "person from clip-art" */}
          <path
            d="M27,55 Q24,90 25,130 Q12,170 5,215 L95,215 Q88,170 75,130 Q76,90 73,55 Q60,46 50,46 Q40,46 27,55 Z"
            fill={color}
          />
        </svg>
      </div>

      <style jsx>{`
        @keyframes ghost-drift-${idSuffix} {
          0% {
            transform: translateX(${direction === "ltr" ? "-30vw" : "calc(100vw + 30vw)"});
          }
          100% {
            transform: translateX(${direction === "ltr" ? "calc(100vw + 30vw)" : "-30vw"});
          }
        }
        @keyframes ghost-bob-${idSuffix} {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-${bob}px); }
        }
      `}</style>
    </div>
  );
}
