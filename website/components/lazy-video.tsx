"use client";

import { useEffect, useRef, useState } from "react";

/**
 * LazyVideo — loops a remote mp4 silently. The video element is only
 * mounted (so the browser only starts the request) once the parent
 * scrolls into the viewport via IntersectionObserver. Plays muted +
 * playsInline so mobile autoplay isn't blocked, and pauses again when
 * the element leaves the viewport to free decode work.
 */
export function LazyVideo({
  src,
  poster,
  className = "",
  rootMargin = "300px",
  preload = "metadata",
}: {
  src: string;
  poster?: string;
  className?: string;
  rootMargin?: string;
  preload?: "none" | "metadata" | "auto";
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [shouldLoad, setShouldLoad] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setShouldLoad(true);
            setVisible(true);
          } else {
            setVisible(false);
          }
        }
      },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [rootMargin]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (visible) v.play().catch(() => {});
    else v.pause();
  }, [visible, shouldLoad]);

  return (
    <div ref={wrapRef} className={className}>
      {shouldLoad ? (
        <video
          ref={videoRef}
          src={src}
          poster={poster}
          autoPlay
          muted
          loop
          playsInline
          preload={preload}
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="w-full h-full bg-surface/40" />
      )}
    </div>
  );
}
