/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./web/templates/**/*.html", "./web/static/js/**/*.js"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        paper: "#fbfaf7",
        panel: "#f4f0ea",
        line: "#e9e4da",
        ink: "#191919",
        cream: "#f5f5f2",
        creamcard: "#e9e8e4",
        skyx: "#b9e5f3",
        zinc: { 850: "rgba(63, 63, 70, 0.45)" },
      },
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
        maison: ['"DM Sans"', "system-ui", "sans-serif"],
        serifit: ['"Instrument Serif"', "Georgia", "serif"],
      },
    },
  },
  safelist: [
    "ring-2",
    "ring-teal-500",
    "-translate-x-full",
    "btn-dark",
    "btn-line",
    "btn-danger",
    "opacity-0",
    "pointer-events-none",
    "translate-y-2",
  ],
};
