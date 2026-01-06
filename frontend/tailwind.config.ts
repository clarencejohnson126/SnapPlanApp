import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Blueprint Pro design colors (desktop MVP)
        bg: {
          primary: '#0F1B2A',    // Deep navy background
          secondary: '#1A2942',  // Card backgrounds
          card: '#243B53',       // Elevated cards
          hover: '#2D4A66',      // Hover states
          // Legacy aliases
          legacy: {
            primary: '#1E3A5F',
            secondary: '#152943',
            card: '#274060',
            hover: '#2d4a6f',
          },
        },
        // Text colors
        text: {
          primary: '#ffffff',
          secondary: '#94A3B8',
          muted: '#64748B',
        },
        // Accent colors
        accent: {
          teal: '#00D4AA',
          blue: '#3B82F6',
          purple: '#A855F7',
          amber: '#F59E0B',
        },
        // Fire rating colors
        fire: {
          t90: '#EF4444',
          t30: '#F59E0B',
          dss: '#FBBF24',
          std: '#6B7280',
        },
        // Border
        border: 'rgba(255, 255, 255, 0.1)',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'card': '0 4px 20px rgba(0, 0, 0, 0.2)',
        'teal': '0 4px 20px rgba(0, 212, 170, 0.4)',
      },
    },
  },
  plugins: [],
}

export default config
