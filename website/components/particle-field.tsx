"use client";

import { useEffect, useRef } from "react";

/**
 * ParticleField — canvas-based constellation network rendered behind the
 * hero. ~80 floating particles connected by faint lines when within
 * proximity. Particles drift on independent vectors, bounce off bounds,
 * and react to mouse movement (repel within radius). Classic AI/data-viz
 * signature without an external lib.
 */
export function ParticleField({
  className = "",
  density = 80,
  color = "rgba(231,181,60,",
  linkColor = "rgba(231,181,60,",
}: {
  className?: string;
  density?: number;
  color?: string;
  linkColor?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let w = 0,
      h = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    const mouse = { x: -1000, y: -1000 };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.scale(dpr, dpr);
    };

    type P = { x: number; y: number; vx: number; vy: number; r: number };
    const particles: P[] = [];
    const seed = () => {
      particles.length = 0;
      for (let i = 0; i < density; i++) {
        particles.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.25,
          vy: (Math.random() - 0.5) * 0.25,
          r: Math.random() * 1.4 + 0.6,
        });
      }
    };

    const linkDist = 140;
    const repelRadius = 130;

    const tick = () => {
      ctx.clearRect(0, 0, w, h);

      // Update + draw particles
      for (const p of particles) {
        // Mouse repel
        const dx = p.x - mouse.x;
        const dy = p.y - mouse.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < repelRadius * repelRadius) {
          const d = Math.max(1, Math.sqrt(d2));
          const force = (repelRadius - d) / repelRadius;
          p.vx += (dx / d) * force * 0.4;
          p.vy += (dy / d) * force * 0.4;
        }

        p.x += p.vx;
        p.y += p.vy;
        // Damping so the field stays calm
        p.vx *= 0.985;
        p.vy *= 0.985;

        // Bounce on bounds
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        p.x = Math.max(0, Math.min(w, p.x));
        p.y = Math.max(0, Math.min(h, p.y));

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0.8)`;
        ctx.fill();
      }

      // Draw links — O(n²) but n=80 is cheap
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i];
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < linkDist * linkDist) {
            const alpha = 1 - Math.sqrt(d2) / linkDist;
            ctx.strokeStyle = `${linkColor}${alpha * 0.18})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      raf = requestAnimationFrame(tick);
    };

    const onMouse = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    const onLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    resize();
    seed();
    raf = requestAnimationFrame(tick);
    window.addEventListener("resize", () => {
      resize();
      seed();
    });
    window.addEventListener("mousemove", onMouse);
    window.addEventListener("mouseout", onLeave);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("mouseout", onLeave);
    };
  }, [density, color, linkColor]);

  return (
    <canvas
      ref={ref}
      className={`pointer-events-none ${className}`}
      aria-hidden="true"
    />
  );
}
