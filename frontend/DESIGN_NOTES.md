# Frontend Design System & Technical Notes (DESIGN_NOTES.md)

**Product**: Business Assistant — Analyst Workbench  
**Design Philosophy**: Calm, precise, editorial, trustworthy tool for professionals (inspired by Linear, Notion, Observable, and bespoke financial research terminals).  
**Strict Exclusions**: No purple/blue gradients, no gradient text, no glowing orbs, no glassmorphism, no rounded-2xl bubbly cards, no emoji bullets, no generic chatbot landing page heroes.

---

## 1. Color System (CSS Variables)

All colors are controlled via CSS variables in `globals.css` and mapped into `tailwind.config.js`.

### Light Theme ("Warm Paper & Dark Ink")
- `--bg-canvas`: `#FAF8F4` (warm textured paper background)
- `--bg-surface`: `#FFFFFF` (crisp white card & panel surfaces)
- `--bg-subtle`: `#F3EFEA` (sidebar, table headers, hovered list rows)
- `--bg-muted`: `#EAE5DE` (code blocks, tag backgrounds)
- `--text-primary`: `#1C1B19` (dense charcoal-black ink)
- `--text-secondary`: `#5E5A54` (readable editorial body copy)
- `--text-muted`: `#8E8A82` (timestamps, table column headers, metadata)
- `--border-subtle`: `#EFECE6` (hairline dividers)
- `--border-default`: `#E2DDD5` (standard 1px container borders)
- `--border-strong`: `#C8C2B8` (inputs, active states, focus rings)
- `--accent`: `#0F6B5F` (deep institutional teal for primary actions and active states)
- `--accent-hover`: `#0B5249` (darker teal on hover)
- `--accent-subtle`: `#E7F2F0` (light teal tint for route pills and badges)
- `--accent-text`: `#0F6B5F` (teal text for badges and links)
- `--accent-contrast`: `#FFFFFF` (pure white text on solid teal buttons)
- `--success`: `#2E7D32` (verified grounded status)
- `--success-subtle`: `#EDF7ED`
- `--warning`: `#B45309` (circuit breaker retries)
- `--warning-subtle`: `#FEF3C7`
- `--danger`: `#C53030` (errors, mutation alerts)
- `--danger-subtle`: `#FEE2E2`

### Dark Theme ("Graphite Desk")
- `--bg-canvas`: `#141413` (rich graphite paper background)
- `--bg-surface`: `#1C1B19` (elevated panels and cards)
- `--bg-subtle`: `#242320` (sidebar, table headers, hovered rows)
- `--bg-muted`: `#2C2B27` (code blocks, tag backgrounds)
- `--text-primary`: `#ECE8E1` (soft off-white ink text)
- `--text-secondary`: `#A8A39A` (readable secondary text)
- `--text-muted`: `#78736B` (metadata and labels)
- `--border-subtle`: `#262522` (hairline dividers)
- `--border-default`: `#32302C` (standard panel borders)
- `--border-strong`: `#4A4742` (inputs, focus rings)
- `--accent`: `#1B8A7C` (luminous teal in dark mode)
- `--accent-hover`: `#25A393`
- `--accent-subtle`: `#142C28`
- `--accent-text`: `#4ECDC4`
- `--accent-contrast`: `#0F1716`
- `--success`: `#48BB78`
- `--success-subtle`: `#132E1E`
- `--warning`: `#F59E0B`
- `--warning-subtle`: `#33220A`
- `--danger`: `#F56565`
- `--danger-subtle`: `#331414`

---

## 2. Typography Hierarchy

Loaded via `next/font/google` for zero-layout-shift and local font bundling:
1. **Editorial Serif**: `Newsreader` (`--font-serif`)
   - Used for: App title, session headline, section headers, document titles.
   - Styling: `font-serif font-medium tracking-tight italic` or `font-serif font-normal`.
2. **Interface Sans**: `IBM Plex Sans` (`--font-sans`)
   - Used for: Body prose, button labels, sidebar items, prompts.
   - Styling: `font-sans text-sm text-secondary leading-relaxed`.
3. **Analytical Mono**: `IBM Plex Mono` (`--font-mono`)
   - Used for: SQL blocks, numeric values (`tabular-nums`), tool names, route tags, citations `[1]`, chunk IDs.
   - Styling: `font-mono text-xs tabular-nums`.

---

## 3. Shape, Depth & Grid Rules

- **Corner Radii**:
  - `rounded-sm` (3px): Buttons, tags, citations, chips.
  - `rounded` (5px): Inputs, code blocks, cards.
  - `rounded-md` (8px): Main panel containers and modals.
  - No `rounded-2xl` or pill buttons.
- **Borders & Shadows**:
  - `1px solid var(--border-default)` on all containers.
  - Box shadows: `none` or ultra-subtle `0 1px 2px rgba(0,0,0,0.04)`.
  - No blur filters (`backdrop-blur`), no glowing outlines.
- **Spacing System**: Strict 4px / 8px grid (`p-2`, `p-3`, `p-4`, `p-6`).

---

## 4. Layout Architecture (3-Pane Analyst Workbench)

```
┌─────────────────┬───────────────────────────────────┬───────────────────────────────┐
│  SLIM SIDEBAR   │        MAIN CONVERSATION          │        EVIDENCE PANEL         │
│     (240px)     │             (Flex-1)              │            (360px)            │
├─────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ • App Branding  │ Top status breadcrumb             │ • Route Chosen (DATA/DOCS/BOTH│
│   (Newsreader)  │ ───────────────────────────────── │ • Tools Called Chain          │
│ • Tabs:         │ Conversation Log / Document View: │ • SQL Statement (Syntax Mono) │
│   - Analysis    │ • Q_01: User question             │ • Tabular Query Result        │
│   - Data Quality│ • Assistant editorial synthesis   │ • Policy Document Chunks      │
│   - Documents   │   with citations [1] [2]          │ • Verification & Retries (0/2)│
│ • Session Log   │ ───────────────────────────────── │                               │
│ • System Status │ Dynamic Input Bar + Status Step   │                               │
│ • Theme Toggle  │ ("Routing" -> "SQL" -> "Checking")│                               │
└─────────────────┴───────────────────────────────────┴───────────────────────────────┘
```

---

## 5. Component Modularization

- `components/Sidebar.jsx`: Navigation, app branding, history, system status pill, theme toggle.
- `components/ChatMessage.jsx`: User question row + Assistant document-style response with inline citation chips.
- `components/EvidencePanel.jsx`: Dedicated right pane with route, tool chain, SQL block, table, document chunks.
- `components/SqlBlock.jsx`: Monospace syntax-highlighted SQL block with copy button and feedback.
- `components/DataTable.jsx`: Compact analytical table with tabular numbers.
- `components/SourceChip.jsx`: Inline citations `[1]`, `[2]` and document badge chips.
- `components/QualityBars.jsx`: Plain CSS before/after metric comparison bars.
- `components/ThemeToggle.jsx`: Accessible dark/light mode toggle with localStorage persistence.
- `components/EmptyState.jsx`: Clean list of sample queries with category badges (`[DATA]`, `[DOCS]`, `[BOTH]`).
- `components/DataQualityView.jsx`: PySpark ETL audit report with summary cards and comparison bars.
- `components/DocumentsView.jsx`: Company policy knowledge base inventory.
- `components/StatusLine.jsx`: Real-time streaming status steps during agent execution.
