import type { Config } from 'tailwindcss'
import forms from '@tailwindcss/forms'
import typography from '@tailwindcss/typography'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#EFF4FB',
          100: '#D0E0F3',
          200: '#A1C1E7',
          300: '#72A2DB',
          400: '#4383CF',
          500: '#1B4F8A',
          600: '#164080',
          700: '#103065',
          800: '#0B2050',
          900: '#061035',
        },
        accent: {
          50:  '#FEF1EC',
          100: '#FCD9CC',
          200: '#F9B399',
          300: '#F68D66',
          400: '#F37033',
          500: '#E85D2F',
          600: '#C44D27',
          700: '#9A3D1F',
          800: '#702D17',
          900: '#461D0F',
        },
        success: {
          50:  '#EEFAF4',
          100: '#D0F0E0',
          200: '#A1E1C1',
          300: '#72D2A2',
          400: '#43C383',
          500: '#1A7A4A',
          600: '#156240',
          700: '#104A30',
          800: '#0B3220',
          900: '#061A10',
        },
        warning: {
          50:  '#FFF8EC',
          100: '#FFEDD0',
          200: '#FFDBA1',
          300: '#FFC972',
          400: '#FFB743',
          500: '#CC7100',
          600: '#B36200',
          700: '#8F4E00',
          800: '#6B3B00',
          900: '#462700',
        },
        danger: {
          50:  '#FEF2F2',
          100: '#FDD9D9',
          200: '#FBB3B3',
          300: '#F98D8D',
          400: '#F56767',
          500: '#B91C1C',
          600: '#9B1818',
          700: '#7D1414',
          800: '#5F1010',
          900: '#410C0C',
        },
        background: '#F8FAFC',
        'dark-text': '#1A1A2E',
      },
      fontFamily: {
        sans:  ['var(--font-inter)', 'system-ui', 'sans-serif'],
        serif: ['var(--font-source-serif)', 'Georgia', 'serif'],
        mono:  ['var(--font-jetbrains-mono)', 'Menlo', 'monospace'],
      },
      fontSize: {
        'disclaimer': ['13px', { lineHeight: '1.5' }],
      },
      borderRadius: {
        'card':  '8px',
        'card-lg': '12px',
      },
      spacing: {
        '4.5': '18px',
      },
      minHeight: {
        'touch': '48px',
      },
      minWidth: {
        'touch': '48px',
      },
      screens: {
        'xs': '375px',
        'sm': '640px',
        'md': '768px',
        'lg': '1024px',
        'xl': '1280px',
        '2xl': '1536px',
      },
    },
  },
  plugins: [forms, typography],
}

export default config
