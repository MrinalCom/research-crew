/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        node: {
          idle: "#8b93a7",
          active: "#8b5cf6",
          done: "#34d399",
          error: "#fb7185",
        },
      },
      backgroundImage: {
        "gemini-gradient": "linear-gradient(115deg, #4f8cff 0%, #a78bfa 45%, #f472b6 100%)",
        "gemini-gradient-soft": "linear-gradient(115deg, rgba(79,140,255,0.18) 0%, rgba(167,139,250,0.18) 45%, rgba(244,114,182,0.18) 100%)",
      },
      boxShadow: {
        glow: "0 0 40px -8px rgba(139,92,246,0.45)",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        shimmer: "shimmer 2.5s linear infinite",
      },
    },
  },
  plugins: [],
};
