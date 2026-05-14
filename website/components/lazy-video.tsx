"use client";

import { useEffect, useRef, useState } from "react";

/**
 * LazyVideo — loops a remote mp4 silently. The video element is only
 * mounted (so the browser only starts the request) once the parent
 * scrolls into the viewport via IntersectionObserver. Without this,
 * loading 6+ cast videos on the marketing page would burn ~30 MB of
 * mobile bandwidth before the user has scrolled to that section.
 *
 * Plays muted + playsInline so autoplay isn't blocked by mobile
 * browsers, and pauses again when the element leaves the viewport
 * to free up decode work.
 */
export function LazyVideo({
  src,
  poster,
  className = "",
}: {
  src: string;
  poster?: string;
  className?: string;
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
      { rootMargin: "200px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (visible) v.play().catch(() => {});
    else v.pause();
  }, [visible, shouldLoad]);

  return (
    <div ref={wrapRef} className={className}>
      {shouldLoad && (
        <video
          ref={videoRef}
          src={src}
          poster={poster}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          className="w-full h-full object-cover"
        />
      )}
      {!shouldLoad && (
        <div className="w-full h-full bg-surface/40" />
      )}
    </div>
  );
}
