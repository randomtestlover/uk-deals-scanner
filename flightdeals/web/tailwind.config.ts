import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1220",
        panel: "#101a2e",
        edge: "#1e2a44",
      },
    },
  },
  plugins: [],
} satisfies Config;
