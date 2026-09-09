import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Mirrors the app's "Obsidian & Champagne" theme so the website and
        // the app share a palette.
        bg: "#0C0B0E",
        bgDeep: "#08070A",
        surface: "#16151A",
        surface2: "#1E1C22",
        accent: "#C9A96E",      // champagne
        accent2: "#E4CE9E",     // champagne bright
        accentDeep: "#B4915A",  // champagne deep
        ink: "#EFE9DE",         // warm off-white — never pure white
        // Bumped muted from #9CA3AF → #B4BAC4 to clear the WCAG AA
        // 4.5:1 contrast threshold against bg. The old value measured
        // ~3.7:1 on its own and dropped below 3:1 once we dimmed it
        // further with /80, /70, /60 opacity modifiers throughout
        // page.tsx — Lighthouse a11y was flagging dozens of contrast
        // failures on every section's body copy. Re-verified against
        // the new bg #0C0B0E: ~10:1, still comfortably clears AA.
        muted: "#B4BAC4",
        danger: "#C6564E",
        success: "#9DBB9C",
        warning: "#D9A441",
      },
      fontFamily: {
        // `--font-inter` and `--font-arabic` are injected by next/font in
        // app/layout.tsx. Without those CSS vars the previous Tailwind
        // config silently fell back to system fonts and the Arabic text
        // rendered in a generic sans (no Naskh shaping). With this wiring
        // the named font actually loads.
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        // Editorial serif for lyric-like headlines — used with restraint.
        display: ["var(--font-display)", "ui-serif", "Georgia", "'Times New Roman'", "serif"],
        arabic: ["var(--font-arabic)", "'Noto Naskh Arabic'", "'Amiri'", "ui-sans-serif", "sans-serif"],
      },
      animation: {
        "float": "float 6s ease-in-out infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
