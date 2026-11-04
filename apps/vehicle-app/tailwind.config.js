/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    '../../packages/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      screens: {
        // Vehicle displays where system bars leave little height; 1280x800 hardware gives only 517 px.
        short: { raw: '(min-width: 768px) and (max-height: 640px)' },
        // Too short for a page introduction and saved values above the Start actions. 1280x800 hardware is 517 px.
        xshort: { raw: '(min-width: 768px) and (max-height: 540px)' },
      },
      colors: {
        togg: {
          turquoise: '#00C2E7',
          darkTurquoise: '#185A7D',
          darkBlue: '#000050',
          teal: '#0E839B',
          glow: 'rgba(0, 194, 231, 0.25)',
          subtle: 'rgba(0, 194, 231, 0.12)'
        },
        cockpit: {
          bg: '#060B12',
          surface: '#0B1320',
          card: '#101B2E',
          border: '#1C2C45',
          accent: '#00C2E7',
          hover: '#33D0EE',
          text: '#F8FAFC',
          muted: '#94A3B8'
        }
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica', 'sans-serif'],
      },
      minHeight: {
        touch: '48px',
        touchLg: '56px'
      }
    },
  },
  plugins: [],
}
