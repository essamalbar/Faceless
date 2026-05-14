"use client";

import { useEffect, useState } from "react";
import { Sparkles, ArrowRight } from "lucide-react";

/**
 * PromptInput — Leonardo.ai-style "type your idea right on the homepage"
 * affordance. A textarea with a cycling placeholder (typewriter effect)
 * and a Generate button that hands the typed premise off to the app's
 * signup flow via a URL param.
 *
 * The marketing value isn't whether the param actually pre-fills the
 * app — it's that visitors feel they can start *now*, without thinking
 * about whether to sign up.
 */
const EXAMPLES = [
  "في قرية معزولة عند سفح الجبل...",
  "كان البئر القديم يحرس أسرار الماضي...",
  "صوت خفيف يأتي من خلف الجدار...",
  "لم يعد إلى البيت ذلك المساء...",
];

export function PromptInput({ appUrl }: { appUrl: string }) {
  const [premise, setPremise] = useState("");
  const [placeholder, setPlaceholder] = useState("");
  const [exIdx, setExIdx] = useState(0);
  const [charIdx, setCharIdx] = useState(0);
  const [deleting, setDeleting] = useState(false);

  // Typewriter cycle through the example premises — types out the
  // current example, pauses, deletes, advances. Stops when the user
  // begins typing (premise non-empty).
  useEffect(() => {
    if (premise.length > 0) return;

    const current = EXAMPLES[exIdx];
    let delay = deleting ? 35 : 70;

    if (!deleting && charIdx === current.length) {
      delay = 1600; // pause at the end
    }
    if (deleting && charIdx === 0) {
      setDeleting(false);
      setExIdx((i) => (i + 1) % EXAMPLES.length);
      return;
    }

    const id = setTimeout(() => {
      if (!deleting) {
        if (charIdx === current.length) setDeleting(true);
        else {
          setCharIdx(charIdx + 1);
          setPlaceholder(current.slice(0, charIdx + 1));
        }
      } else {
        setCharIdx(charIdx - 1);
        setPlaceholder(current.slice(0, charIdx - 1));
      }
    }, delay);

    return () => clearTimeout(id);
  }, [exIdx, charIdx, deleting, premise]);

  return (
    <form
      method="get"
      action={`${appUrl}/`}
      className="relative w-full max-w-2xl"
    >
      <div className="group relative rounded-2xl border border-white/15 bg-black/55 backdrop-blur-xl shadow-2xl shadow-black/40 overflow-hidden hover:border-accent/50 focus-within:border-accent/70 transition-colors">
        {/* Subtle inner glow on focus */}
        <div className="absolute inset-0 pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity"
             style={{
               background: "radial-gradient(ellipse 100% 60% at 50% 50%, rgba(231,181,60,0.08), transparent 70%)",
             }} />
        <textarea
          name="premise"
          value={premise}
          onChange={(e) => setPremise(e.target.value)}
          placeholder={placeholder || EXAMPLES[0]}
          rows={2}
          dir="auto"
          className="relative w-full bg-transparent text-ink placeholder:text-muted/60 px-5 pt-5 pb-3 text-base sm:text-lg leading-relaxed resize-none outline-none font-arabic"
        />
        <div className="relative flex items-center justify-between px-3 pb-3 pt-1">
          <div className="flex items-center gap-2 px-2 text-[11px] text-muted/70">
            <Sparkles className="w-3 h-3 text-accent" />
            One line is enough
          </div>
          <button
            type="submit"
            className="group/btn bg-accent text-bg font-semibold text-sm px-4 py-2 rounded-lg flex items-center gap-1.5 hover:bg-accent/90 transition-all hover:scale-[1.02]"
          >
            Generate
            <ArrowRight className="w-3.5 h-3.5 group-hover/btn:translate-x-0.5 transition-transform" />
          </button>
        </div>
      </div>
    </form>
  );
}
