/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f1117',
          1: '#151821',
          2: '#1c2030',
          3: '#242840',
        },
        brand: {
          DEFAULT: '#3b82f6',
          dim: '#1d4ed8',
        },
        success: '#22c55e',
        warning: '#f59e0b',
        danger: '#ef4444',
        critical: '#dc2626',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
