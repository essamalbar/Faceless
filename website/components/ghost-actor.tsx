"use client";

/**
 * GhostActor — a real photographed silhouette of a person in fog that
 * drifts across its parent section like a real shadow crossing a stage.
 *
 * Uses an Unsplash photo (cropped to a vertical strip via object-cover
 * + object-position) so the figure is photorealistic — the user
 * explicitly rejected the cartoonish SVG walk-cycle approach in
 * favour of something that reads as a real human.
 *
 * Animation is pure CSS keyframes: a horizontal translate-X traversal
 * across the parent, plus a 1.2s vertical bob to suggest walking gait
 * without needing per-limb animation.
 */
export function GhostActor({
  photo = "1486312338219-ce68d2c6f44d",   // person walking away
  direction = "ltr",
  bottom = "0%",
  height = 520,
  opacity = 0.72,
  duration = 24,
  delay = 0,
  objectPosition = "center bottom",
}: {
  /** Unsplash photo ID (the part after `photo-` in the URL). Defaults
      to a person-walking-away shot, which crops well to vertical. */
  photo?: string;
  /** Direction of travel across the parent */
  direction?: "ltr" | "rtl";
  /** Distance from the parent's bottom (CSS value). Figure stands on
      this line so the feet stay grounded. */
  bottom?: string;
  /** Figure height in pixels. 520 reads as tall human silhouette next
      to typical hero typography. */
  height?: number;
  /** Final shadow opacity. Higher = more solid, lower = misty */
  opacity?: number;
  /** Seconds for one full traversal */
  duration?: number;
  /** Seconds to wait before the first traversal */
  delay?: number;
  /** object-position for the cropped photo. Default centers the figure
      with feet aligned to bottom. */
  objectPosition?: string;
}) {
  const id = `${direction}-${duration}-${delay}`.replace(/\./g, "");
  const src = `https://images.unsplash.com/photo-${photo}?w=400&q=80&auto=format&fit=crop`;
  return (
    <div
      className="pointer-events-none absolute z-[1]"
      style={{
        bottom,
        height,
        width: height * 0.4,
        opacity,
        animationName: `drift-${id}`,
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
        animationIterationCount: "infinite",
        animationTimingFunction: "linear",
        // Hard ground shadow under the feet so the figure feels real,
        // not a floating sticker
        filter: "drop-shadow(0 14px 28px rgba(0,0,0,0.75))",
      }}
    >
      <div
        className="w-full h-full"
        style={{
          animationName: `bob-${id}`,
          animationDuration: "1.1s",
          animationIterationCount: "infinite",
          animationTimingFunction: "ease-in-out",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt=""
          loading="lazy"
          className="w-full h-full"
          style={{
            objectFit: "cover",
            objectPosition,
            // Mirror the figure horizontally for right-to-left travel
            // so the person appears to face their direction of motion
            transform: direction === "rtl" ? "scaleX(-1)" : undefined,
            // Heavy darkening + slight blur so the photo reads as a
            // shadow/silhouette in fog rather than a clean stock
            // photo dropped on top of the page
            filter: "brightness(0.4) contrast(1.4) saturate(0.5) blur(0.6px)",
            // Fade the top and side edges into the page so the figure
            // looks like it materialises out of haze, not like a
            // rectangular cutout
            maskImage:
              "linear-gradient(to bottom, transparent 0%, black 22%, black 100%), linear-gradient(to right, transparent 0%, black 18%, black 82%, transparent 100%)",
            WebkitMaskImage:
              "linear-gradient(to bottom, transparent 0%, black 22%, black 100%), linear-gradient(to right, transparent 0%, black 18%, black 82%, transparent 100%)",
            maskComposite: "intersect",
            WebkitMaskComposite: "source-in",
          }}
        />
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
          50%      { transform: translateY(-7px); }
        }
      `}</style>
    </div>
  );
}
