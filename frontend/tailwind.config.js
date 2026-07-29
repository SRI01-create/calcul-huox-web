/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // Couleurs sémantiques pour les ratios EC3
      colors: {
        ratio: {
          ok:      '#16a34a', // vert   < 0.5
          warning: '#d97706', // orange 0.5 – 0.9
          danger:  '#dc2626', // rouge  0.9 – 1.0
          over:    '#7f1d1d', // rouge foncé > 1.0
        },
      },
    },
  },
  plugins: [],
}
