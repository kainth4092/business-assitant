/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./lib/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "var(--bg-paper)",
        raised: "var(--bg-raised)",
        sunken: "var(--bg-sunken)",
        grid: "var(--grid-line)",
        "grid-strong": "var(--grid-strong)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        seal: {
          DEFAULT: "var(--seal-red)",
          ink: "var(--seal-red-ink)",
          tint: "var(--seal-red-tint)",
          on: "var(--seal-ink-on)",
        },
        highlighter: {
          DEFAULT: "var(--highlighter)",
          wash: "var(--highlighter-wash)",
          ink: "var(--highlighter-ink)",
        },
        sage: {
          DEFAULT: "var(--sage)",
          ink: "var(--sage-ink)",
          tint: "var(--sage-tint)",
        },
        amber: {
          DEFAULT: "var(--amber)",
          ink: "var(--amber-ink)",
          tint: "var(--amber-tint)",
        },
        route: {
          data: {
            DEFAULT: "var(--route-data)",
            ink: "var(--route-data-ink)",
            tint: "var(--route-data-tint)",
          },
          docs: {
            DEFAULT: "var(--route-docs)",
            ink: "var(--route-docs-ink)",
            tint: "var(--route-docs-tint)",
          },
          both: {
            DEFAULT: "var(--route-both)",
            ink: "var(--route-both-ink)",
            tint: "var(--route-both-tint)",
          },
        },
      },
      fontFamily: {
        serif: [
          "var(--font-serif)",
          '"Shippori Mincho"',
          '"Hiragino Mincho ProN"',
          "Georgia",
          "serif",
        ],
        sans: [
          "var(--font-sans)",
          '"Zen Kaku Gothic New"',
          '"Hiragino Sans"',
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        none: "0px",
        xs: "2px",
        sm: "2px",
        DEFAULT: "2px",
        md: "2px",
        lg: "2px",
      },
      boxShadow: {
        stack: "var(--shadow-stack)",
        "stack-strong": "var(--shadow-stack-strong)",
      },
    },
  },
  plugins: [],
};
