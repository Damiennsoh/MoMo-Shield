import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#06090F",
          900: "#0A0F1A",
          800: "#101828",
          700: "#16213A",
          600: "#1F2D4A",
          500: "#2B3D61",
        },
        accent: {
          DEFAULT: "#FACC15",
          dim: "#C9A40E",
        },
        risk: {
          high: "#EF4444",
          medium: "#F59E0B",
          low: "#22C55E",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      boxShadow: {
        "glow-high": "0 0 24px rgba(239,68,68,0.35)",
        "glow-accent": "0 0 20px rgba(250,204,21,0.25)",
        panel: "0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.4)",
      },
      animation: {
        "pulse-ring": "pulseRing 1.6s cubic-bezier(0.4,0,0.2,1) infinite",
        "fade-up": "fadeUp 0.4s ease-out both",
        blink: "blink 1s step-end infinite",
      },
      keyframes: {
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgba(239,68,68,0.5)" },
          "70%": { boxShadow: "0 0 0 12px rgba(239,68,68,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(239,68,68,0)" },
        },
        fadeUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
