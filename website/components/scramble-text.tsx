"use client";

import { useEffect, useState } from "react";

const CHARS = "▓▒░ABCDEFGHIJKLMNOPQRSTUVWXYZ01010101";

/**
 * ScrambleText — animates `text` from a random-character scramble to the
 * actual string, classic Matrix-style decrypt effect. Runs once on mount.
 * Tasteful for short strings (eyebrow chips, labels); don't use on body
 * paragraphs.
 */
export function ScrambleText({
  text,
  duration = 1100,
  className = "",
}: {
  text: string;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(text);

  useEffect(() => {
    const start = performance.now();
    let raf = 0;

    const tick = (t: number) => {
      const elapsed = t - start;
      const progress = Math.min(1, elapsed / duration);
      // resolveAt[i] = fraction of duration when character i should lock
      const resolved = Math.floor(progress * text.length);
      let out = "";
      for (let i = 0; i < text.length; i++) {
        if (i < resolved || text[i] === " ") {
          out += text[i];
        } else {
          out += CHARS[Math.floor(Math.random() * CHARS.length)];
        }
      }
      setDisplay(out);
      if (progress < 1) raf = requestAnimationFrame(tick);
      else setDisplay(text);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, duration]);

  return <span className={className}>{display}</span>;
}
