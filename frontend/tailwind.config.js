/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f5f7ff',
          100: '#ebf0fe',
          500: '#4361ee',
          600: '#3a0ca3',
          700: '#2b0975',
        }
      }
    },
  },
  plugins: [],
}

