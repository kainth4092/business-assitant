/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        page: 'var(--bg-page)',
        canvas: 'var(--bg-page)',
        surface: 'var(--bg-surface)',
        'surface-lowest': 'var(--bg-surface-lowest)',
        'surface-low': 'var(--bg-surface-low)',
        'surface-container': 'var(--bg-surface-container)',
        'surface-high': 'var(--bg-surface-high)',
        'surface-highest': 'var(--bg-surface-highest)',
        sunken: 'var(--bg-surface-container)',

        primary: 'var(--text-primary)',
        ink: 'var(--text-primary)',
        muted: 'var(--text-muted)',
        'text-muted': 'var(--text-muted)',

        border: 'var(--border-default)',
        'border-default': 'var(--border-default)',
        'border-subtle': 'var(--border-subtle)',
        'border-strong': 'var(--border-strong)',

        'accent-lime': {
          DEFAULT: 'var(--accent-lime)',
          hover: 'var(--accent-lime-hover)',
          contrast: 'var(--accent-lime-contrast)',
          subtle: 'var(--accent-lime-subtle)',
          border: 'var(--accent-lime-border)',
        },
        'accent-cyan': {
          DEFAULT: 'var(--accent-cyan)',
          subtle: 'var(--accent-cyan-subtle)',
          border: 'var(--accent-cyan-border)',
        },
        'accent-amber': {
          DEFAULT: 'var(--accent-amber)',
          subtle: 'var(--accent-amber-subtle)',
          border: 'var(--accent-amber-border)',
        },
        'accent-emerald': {
          DEFAULT: 'var(--accent-emerald)',
          subtle: 'var(--accent-emerald-subtle)',
          border: 'var(--accent-emerald-border)',
        },
        'accent-crimson': {
          DEFAULT: 'var(--accent-crimson)',
          subtle: 'var(--accent-crimson-subtle)',
          border: 'var(--accent-crimson-border)',
        },

        // Compatibility Aliases for components
        accent: {
          DEFAULT: 'var(--accent-lime)',
          hover: 'var(--accent-lime-hover)',
          contrast: 'var(--accent-lime-contrast)',
          subtle: 'var(--accent-lime-subtle)',
          text: 'var(--accent-lime)',
        },
        route: {
          data: {
            DEFAULT: 'var(--accent-cyan)',
            subtle: 'var(--accent-cyan-subtle)',
            border: 'var(--accent-cyan-border)',
          },
          docs: {
            DEFAULT: 'var(--accent-amber)',
            subtle: 'var(--accent-amber-subtle)',
            border: 'var(--accent-amber-border)',
          },
          both: {
            DEFAULT: 'var(--accent-lime)',
            subtle: 'var(--accent-lime-subtle)',
            border: 'var(--accent-lime-border)',
          },
        },
        semantic: {
          success: {
            DEFAULT: 'var(--accent-emerald)',
            subtle: 'var(--accent-emerald-subtle)',
          },
          warning: {
            DEFAULT: 'var(--accent-amber)',
            subtle: 'var(--accent-amber-subtle)',
          },
          error: {
            DEFAULT: 'var(--accent-crimson)',
            subtle: 'var(--accent-crimson-subtle)',
          },
        },
      },
      fontFamily: {
        headline: ['var(--font-headline)', 'Space Grotesk', 'sans-serif'],
        serif: ['var(--font-headline)', 'Space Grotesk', 'sans-serif'],
        body: ['var(--font-body)', 'IBM Plex Sans', 'sans-serif'],
        sans: ['var(--font-body)', 'IBM Plex Sans', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'headline-xl': ['32px', { lineHeight: '40px', letterSpacing: '-0.02em', fontWeight: '700' }],
        'headline-lg': ['24px', { lineHeight: '28px', letterSpacing: '-0.015em', fontWeight: '600' }],
        'headline-md': ['18px', { lineHeight: '24px', letterSpacing: '-0.01em', fontWeight: '600' }],
        'title': ['28px', { lineHeight: '34px', letterSpacing: '-0.02em', fontWeight: '700' }],
        'body-lg': ['16px', { lineHeight: '24px' }],
        'body-md': ['14px', { lineHeight: '20px' }],
        'body-sm': ['12px', { lineHeight: '16px' }],
        'body-base': ['14px', { lineHeight: '22px' }],
        'metric-display': ['28px', { lineHeight: '32px', letterSpacing: '-0.03em', fontWeight: '700' }],
        'label-telemetry': ['11px', { lineHeight: '14px', letterSpacing: '0.06em', fontWeight: '600' }],
        'section-label': ['11px', { lineHeight: '14px', letterSpacing: '0.06em', fontWeight: '600' }],
        'code-md': ['12px', { lineHeight: '18px' }],
        'tag': ['11px', { lineHeight: '14px', fontWeight: '700', letterSpacing: '0.04em' }],
      },
      borderRadius: {
        xs: '2px',
        sm: '4px',
        DEFAULT: '6px',
        md: '8px',
        lg: '10px',
        xl: '12px',
        full: '9999px',
      },
      boxShadow: {
        xs: '0 1px 2px rgba(28, 32, 36, 0.05)',
        sm: '0 1px 2px rgba(28, 32, 36, 0.05)',
        card: '0 1px 2px rgba(28, 32, 36, 0.04), 0 4px 12px -2px rgba(28, 32, 36, 0.06)',
        'card-hover': '0 4px 12px rgba(28, 32, 36, 0.08), 0 1px 3px rgba(28, 32, 36, 0.06)',
        composer: '0 2px 8px rgba(28, 32, 36, 0.06), 0 16px 32px -8px rgba(28, 32, 36, 0.12)',
      },
      transitionDuration: {
        fast: '150ms',
        normal: '200ms',
        smooth: '300ms',
      },
    },
  },
  plugins: [],
};
