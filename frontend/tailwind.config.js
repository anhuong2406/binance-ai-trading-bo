/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          darkest: '#080B10',
          darker: '#0D1117',
          dark: '#161B22',
          card: '#1F242C',
          border: '#30363D',
        },
        bloomberg: {
          orange: '#FF9900',
          amber: '#F59E0B',
          cyan: '#00E5FF',
          green: '#00E676',
          red: '#FF1744',
          gray: '#8B949E',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
