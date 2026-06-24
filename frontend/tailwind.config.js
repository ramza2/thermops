/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#1e40af", foreground: "#ffffff" },
        sidebar: { DEFAULT: "#0f172a", foreground: "#cbd5e1", accent: "#1e293b" },
      },
    },
  },
  plugins: [],
};
