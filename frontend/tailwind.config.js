/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#2C7A6B",
        secondary: "#F4F4F4",
        accent: "#FFB74D",
        dark: "#1E2A2E",
      },
      fontFamily: {
        sans: ['Noto Sans', 'Noto Sans Tamil', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
