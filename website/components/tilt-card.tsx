"use client";

import { useRef, useState, type ReactNode } from "react";

/**
 * TiltCard — a wrapper that gives its child a vanilla-tilt feel: the
 * card rotates toward the cursor in 3D and shows a soft radial highlight
 * where the cursor sits. Disabled on touch devices (handled by CSS
 * media + the absence of mousemove events).
 */
export function TiltCard({
  children,
  className = "",
  maxTilt = 12,
  scale = 1.03,
}: {
  children: ReactNode;
  className?: string;
  maxTilt?: number;
  scale?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [t, setT] = useState({ rx: 0, ry: 0, px: 50, py: 50 });

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;  // 0..1
    const y = (e.clientY - r.top) / r.height;  // 0..1
    setT({
      rx: (0.5 - y) * maxTilt * 2,   // tilt up when cursor at top
      ry: (x - 0.5) * maxTilt * 2,   // tilt right when cursor at right
      px: x * 100,
      py: y * 100,
    });
  };

  const onLeave = () => setT({ rx: 0, ry: 0, px: 50, py: 50 });

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{
        transform: `perspective(1200px) rotateX(${t.rx}deg) rotateY(${t.ry}deg) scale(${t.rx || t.ry ? scale : 1})`,
        transformStyle: "preserve-3d",
        transition: "transform 0.25s ease-out",
      }}
      className={`relative ${className}`}
    >
      {children}
      {/* Cursor highlight — radial gradient at cursor position, only
          visible while hovering (rx/ry non-zero). pointer-events-none so
          it never intercepts the actual link/click. */}
      <div
        className="absolute inset-0 rounded-[inherit] pointer-events-none mix-blend-overlay transition-opacity duration-300"
        style={{
          opacity: t.rx === 0 && t.ry === 0 ? 0 : 1,
          background: `radial-gradient(circle at ${t.px}% ${t.py}%, rgba(255,255,255,0.18), transparent 50%)`,
        }}
      />
    </div>
  );
}
