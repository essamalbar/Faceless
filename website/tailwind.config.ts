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
        // Phase 1 bumped muted off the original #9CA3AF to clear the WCAG
        // AA 4.5:1 contrast threshold against bg. Phase 2 fold-in: swapped
        // that cool-tinted intermediate value for the app's warm secondary
        // #A39C8E (matches the app's textSecondary) so the site's muted
        // text reads consistently with the app. Contrast against bg
        // #0C0B0E is ~7:1, still comfortably clears the 4.5:1 AA floor.
        muted: "#A39C8E",
        danger: "#C6564E",
        success: "#9DBB9C",
        warning: "#D9A441",
      },
      fontFamily: {
        // `--font-inter`, `--font-arabic` and `--font-display` are injected
        // by next/font in app/layout.tsx (var names unchanged since Phase 1
        // — only the font families bound to them changed, to Manrope /
        // Amiri / Cormorant Garamond, matching the app's editorial pairing).
        // Without those CSS vars Tailwind would silently fall back to
        // system fonts.
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        // Editorial serif for lyric-like headlines — used with restraint.
        display: ["var(--font-display)", "Georgia", "serif"],
        arabic: ["var(--font-arabic)", "'Noto Naskh Arabic'", "serif"],
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
