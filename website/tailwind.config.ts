import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Mirrors lib/theme.dart so the website and the app share a palette.
        bg: "#0A0E1A",
        surface: "#121828",
        surface2: "#1A2238",
        accent: "#E7B53C",      // brand gold
        accent2: "#8B5CF6",     // violet for variety
        rose: "#EC8FA9",        // warm rose — the middle note of the stage-light gradient
        ink: "#E5E7EB",
        // Bumped muted from #9CA3AF → #B4BAC4 to clear the WCAG AA
        // 4.5:1 contrast threshold against bg #0A0E1A. The old value
        // measured ~3.7:1 on its own and dropped below 3:1 once we
        // dimmed it further with /80, /70, /60 opacity modifiers
        // throughout page.tsx — Lighthouse a11y was flagging dozens of
        // contrast failures on every section's body copy.
        muted: "#B4BAC4",
        danger: "#EF4444",
        success: "#10B981",
        warning: "#F59E0B",
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
