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
        ink: "#E5E7EB",
        muted: "#9CA3AF",
        danger: "#EF4444",
        success: "#10B981",
        warning: "#F59E0B",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        arabic: ["'Noto Naskh Arabic'", "'Amiri'", "ui-sans-serif", "sans-serif"],
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
