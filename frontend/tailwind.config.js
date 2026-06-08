/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
      },
      colors: {
        ink: { 950: '#0a0f1e', 900: '#0f172a', 700: '#334155' },
      },
      keyframes: {
        fadeUp: { from: { opacity: 0, transform: 'translateY(12px)' },
                  to: { opacity: 1, transform: 'translateY(0)' } },
      },
      animation: { fadeUp: 'fadeUp .4s ease-out forwards' },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
