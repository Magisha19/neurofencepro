/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: "rgb(var(--color-bg) / <alpha-value>)",
          900: "rgb(var(--color-surface) / <alpha-value>)",
          800: "rgb(var(--color-surface-raised) / <alpha-value>)",
          700: "rgb(var(--color-border) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--color-accent) / <alpha-value>)",
          muted: "rgb(var(--color-accent-muted) / <alpha-value>)",
        },
        risk: {
          low: "rgb(var(--color-risk-low) / <alpha-value>)",
          moderate: "rgb(var(--color-risk-moderate) / <alpha-value>)",
          high: "rgb(var(--color-risk-high) / <alpha-value>)",
          critical: "rgb(var(--color-risk-critical) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 18px 60px rgb(0 0 0 / 0.28)",
      },
    },
  },
  plugins: [],
};
