import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))', foreground: 'hsl(var(--foreground))',
        card: 'hsl(var(--card))', border: 'hsl(var(--border))', muted: 'hsl(var(--muted))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
      },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], mono: ['ui-monospace', 'SFMono-Regular', 'monospace'] },
      boxShadow: { glow: '0 0 24px rgba(255,204,0,.14)' },
      animation: { 'pulse-soft': 'pulse-soft 2.5s ease-in-out infinite', 'slide-up': 'slide-up .35s ease-out' },
      keyframes: {
        'pulse-soft': { '0%,100%': { opacity: '.55', transform: 'scale(.92)' }, '50%': { opacity: '1', transform: 'scale(1.08)' } },
        'slide-up': { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
};
export default config;
