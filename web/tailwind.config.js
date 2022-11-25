const defaultTheme = require("tailwindcss/defaultTheme");

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx,jsx,js}"],
  theme: {
    extend: {
      colors: {
        brand: "#cc6666",
        midnight: "#2c2c2c",
      },
      fontSize: {
        xxs: "0.625rem",
      },
      fontFamily: {
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
        display: ["Lexend", ...defaultTheme.fontFamily.sans],
        mono: ["Roboto Mono", ...defaultTheme.fontFamily.mono],
      },
      maxWidth: {
        narrow: "10rem",
        xxs: "15rem",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
