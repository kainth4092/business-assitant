# Design System & Technical Notes: Business Assistant Workbench

## 1. Design Direction & Product Philosophy

The **Business Assistant** interface is designed as an **editorial analyst workbench** (drawing inspiration from tools like *Linear*, *Notion*, and *Observable*), departing completely from generic AI chatbot landing page templates.

### Core Principles
- **Editorial & Precise**: Dense, calm, trustworthy presentation prioritizing data readability, contrast, and verification over decorative flair.
- **Audit-First**: Transparent evidence and execution traces are the primary visual feature, proving that the agent uses verifiable SQL queries and pgvector document citations rather than hallucinating.
- **Log / Document Layout**: The conversation flow avoids bubble chat avatars and instead formats questions as crisp prompt entries (`YOU · Q_01`) and answers as editorial prose with inline citation chips (`[1]`, `[2]`).
- **No Generative AI Cliches**: Zero purple/pink gradients, neon glowing orbs, blurred backdrop blobs, bubbly rounded-2xl cards, or emojis. Every icon uses `lucide-react` with a clean `1.75px-2px` stroke.

---

## 2. Color System & Semantic Tokens

All styling is built on semantic CSS custom properties defined in `frontend/app/globals.css` and mapped in `frontend/tailwind.config.js`.

### Palette Specifications

| Token Name | Light Theme ("Warm Paper") | Dark Theme ("Slate Editorial") | Usage / Contrast |
| :--- | :--- | :--- | :--- |
| `--bg-page` | `#F6F1E7` (Warm paper) | `#12110F` (Deep carbon ink) | Main document background with 3% dot texture |
| `--bg-surface` | `#FFFDF8` (Warm white surface) | `#1B1A17` (Subtle dark surface) | Cards, sidebars, panels, inputs |
| `--bg-sunken` | `#EDE6D8` (Sand stone fill) | `#0D0C0B` (Sunken well fill) | Badges, code containers, table headers |
| `--text-ink` | `#1B1A17` (Near-black ink) | `#F3EEE2` (Off-white parchment) | Headings, primary body prose (AAA > 14:1) |
| `--text-muted` | `#5E584B` (Dark olive charcoal) | `#B3AC9B` (Warm neutral gray) | Captions, metadata, labels (**AA > 5.27:1**, never faint) |
| `--border-default` | `#D9D0BC` (1px warm gray border) | `#33302A` (1px dark steel border)| Structural 1px separation lines |
| `--border-strong` | `#BFB59E` (Darker separation line) | `#47433B` (Stronger dark border) | Active states, hover borders |
| `--accent` | `#0B6E64` (Deep institutional teal)| `#3FBFAE` (Luminous teal) | Primary button, active tab bar, focus rings |

### Three Route Colors (Used Consistently)

| Route | Primary Color | Soft Tinted Background | Border Accent | Application |
| :--- | :--- | :--- | :--- | :--- |
| **DATA** | `#0B6E64` (Dark: `#3FBFAE`) | `rgba(11, 110, 100, 0.11)` | `rgba(11, 110, 100, 0.35)` | SQL queries, sales tables, data starters |
| **DOCS** | `#B45309` (Dark: `#F59E0B`) | `rgba(180, 83, 9, 0.11)` | `rgba(180, 83, 9, 0.35)` | pgvector retrieval, policies, doc starters |
| **BOTH** | `#3B3F8F` (Dark: `#818CF8`) | `rgba(59, 63, 143, 0.11)` | `rgba(59, 63, 143, 0.35)` | Hybrid SQL + RAG questions, synthesis |

### Semantic Tokens
- **Success**: `#15803D` (Light) / `#4ADE80` (Dark) with 10% tinted background.
- **Warning**: `#B45309` (Light) / `#FBBF24` (Dark) with 10% tinted background.
- **Error**: `#B91C1C` (Light) / `#F87171` (Dark) with 10% tinted background.

---

## 3. Typography Hierarchy

Fonts are loaded locally via `next/font/google` with zero layout shift:

1. **Headings & App Identity (`--font-serif`)**: `Newsreader` (weights: 400, 500, 600, style: normal & italic).
   - Page Title: `30-34px` (`font-serif font-semibold text-title`).
   - Card Titles & Section Headings: `16-18px font-bold`.
2. **Interface & Prose (`--font-sans`)**: `IBM Plex Sans` (weights: 400, 500, 600).
   - Section Labels: `12px` uppercase with `0.08em` letter-spacing in `#5E584B` (WCAG AA).
   - Body Text: `15px / 1.6` line-height for comfortable editorial reading.
   - Tag Badges: `11.5px font-bold` with `0.02em` tracking.
3. **Data, Code, & Tool Traces (`--font-mono`)**: `IBM Plex Mono` (weights: 400, 500, 600, tabular figures).
   - Used for SQL query blocks, row counts, cosine distance metrics, file paths (`docs/*.md`), and tool execution logs.

---

## 4. Spacing, Geometry & Visual Depth

- **Spacing Grid**: Strict 4px / 8px scale (`gap-1` = 4px, `gap-2` = 8px, `gap-3` = 12px, `gap-4` = 16px, `p-6` = 24px).
- **Border Radii**: Restrained radii (`rounded-sm`: 4px, `rounded`: 6px, `rounded-md`: 8px).
- **Depth**: True 1px borders combined with layered surfaces (`bg-page` -> `bg-surface` -> `bg-sunken`) and subtle shadow levels:
  - `shadow-card`: `0 1px 2px rgba(0,0,0,.05), 0 8px 24px -12px rgba(0,0,0,.12)`
  - `shadow-composer`: `0 2px 4px rgba(0,0,0,.04), 0 12px 32px -12px rgba(0,0,0,.16)`
- **Background Texture**: 3.5% opacity dot-grid radial pattern (`radial-gradient(var(--dot-pattern) 1px, transparent 1px)`) sized at 20px x 20px.

---

## 5. Motion Rules & Timing

All animations are lightweight, subtle, and respect `prefers-reduced-motion`:
- **Staggered Page Load**: Hero, stat tiles, and starter rows animate with 60ms stagger, 300ms duration, and 8px translate (`animate-fade-up`).
- **Interactive Hovers**: Starter row lifts 2px (`hover:-translate-y-0.5`), shadow increases, and right arrow slides (`group-hover:translate-x-1`) in 150ms.
- **Button Press**: Active button press scales to `0.98` (`active:scale-[0.98]`).
- **Segmented Control**: Sliding highlight pill between Auto, Data, Docs, and Both.
- **Agent Execution**: Step-by-step status line with glowing soft pulse node (`animate-pulse-soft`) and sequential trace timeline illumination. NO bouncing dots or spinner-only loading.
- **Count-Up Animation**: Stat tiles (sales rows, policy chunks, tools) animate from 0 to target over 600ms once on initial mount.
- **Theme Switcher**: Smooth 150-200ms color transition across CSS variables.
- **Speed Cap**: No animation exceeds 400ms (except the 600ms count-up).

---

## 6. Three-Pane Workbench Architecture

```
+-------------------+-----------------------------------+-----------------------+
|  SLIM SIDEBAR     |      MAIN CONVERSATION COLUMN     |    EVIDENCE PANEL     |
|  (256px fixed)    |         (Editorial Log View)      |   (384px fixed/sheet) |
|                   |                                   |                       |
| - Logo Mark (SVG) | - Sticky breadcrumb bar           | - Tabs: Trace, SQL,   |
| - "New Analysis"  | - Hero with 3 Stat Tiles          |   Results, Sources    |
| - 3px Accent Bar  | - 5 Route-Bordered Starters       | - Vertical Timeline   |
|   Active Nav Items| - Q_01, Q_02 question entries     |   with colored nodes  |
| - Session History | - Answer card with route border   | - Syntax SQL + Copy   |
| - High-contrast   | - Inline citation chips [1], [2]  | - Zebra table results |
|   telemetry card  | - Real-time StatusLine progress   | - Vector chunks with  |
| - Theme Toggle    | - Raised Composer with Segmented  |   cosine similarity   |
|                   |   Route Selector (Auto/Data/Docs) | - Groundedness badge  |
+-------------------+-----------------------------------+-----------------------+
```

### Mobile & Tablet Adaptation
- On screens `< 1024px` (LG), the sidebar collapses into a slide-over drawer accessible via the top-left hamburger menu.
- On screens `< 640px` (mobile), the Evidence panel opens as a responsive bottom sheet (`max-h-[82vh] rounded-t-xl`) with drag handle, preventing any horizontal overflow on 390px mobile screens. On tablet (640-1280px), it opens as a slide-over drawer.

---

## 7. Component Directory

| Component | File Path | Key Polish & Features |
| :--- | :--- | :--- |
| `Sidebar` | `frontend/components/Sidebar.jsx` | Overlapping square SVG logo, 3px left border on active nav item, real counters, high-contrast Postgres telemetry card, theme toggle. |
| `EmptyState` | `frontend/components/EmptyState.jsx` | 30px Newsreader title, capabilities strip with 3 stat tiles (sales rows, chunks, tools) with 600ms count-up, 5 starters with route-colored left borders and hover lift. |
| `ChatMessage` | `frontend/components/ChatMessage.jsx` | `YOU · Q_01` user prompt line, assistant answer card with 3.5px left border in route color, route pill, inline clickable citation chips, copy button. |
| `EvidencePanel` | `frontend/components/EvidencePanel.jsx` | 4 Tabs (`Trace`, `SQL`, `Results`, `Sources`), vertical execution timeline with colored step nodes, groundedness status, syntax SQL, zebra results table. |
| `SqlBlock` | `frontend/components/SqlBlock.jsx` | Dark terminal mono block, high-contrast keyword highlighting (`SELECT`, `SUM`, `GROUP BY`), copy button with toast feedback. |
| `DataTable` | `frontend/components/DataTable.jsx` | Zebra striping, right-aligned tabular figures for numbers, row count badge, clean borders. |
| `SourceChip` | `frontend/components/SourceChip.jsx` | High-contrast interactive inline chip opening matching vector chunk in evidence panel. |
| `QualityBars` | `frontend/components/QualityBars.jsx` | High-contrast before/after comparison bars with bold tabular figures and accent progress. |
| `StatusLine` | `frontend/components/StatusLine.jsx` | Multi-step progress indicator with soft pulsing node (no bouncing dots). |
| `DataQualityView` | `frontend/components/DataQualityView.jsx` | PySpark ETL audit with big numbers, null imputations, fat content standardization cards, and before/after comparison bars. |
| `DocumentsView` | `frontend/components/DocumentsView.jsx` | High-contrast pgvector catalog, chunk statistics, search filter, and instant query buttons. |
| `ThemeToggle` | `frontend/components/ThemeToggle.jsx` | High-contrast Light/Dark switch with smooth transitions. |
| `page.jsx` | `frontend/app/page.jsx` | 3-pane workbench layout, raised composer card with segmented route control (Auto / Data / Docs / Both), mobile bottom sheet support. |

---

## 8. Verification & Build Confirmation

- **TypeScript Free**: Verified 100% JavaScript (`.jsx`).
- **ESLint**: Passed with `0 warnings, 0 errors` via Next.js core web vitals.
- **Production Build**: Verified with `npm run build` yielding fully optimized standalone static bundles (`18.8 kB` index route, `106 kB` first load JS).
- **Contrast Check**: All secondary texts verified to exceed WCAG AA (`#5E584B` on `#F6F1E7` = 5.27:1; `#B3AC9B` on `#1B1A17` = 6.45:1).


---

## 9. Stitch Design System Implementation ("Live Agent Business Assistant")

In accordance with the project specification, the entire frontend was rebuilt to match the design system from the Stitch workspace project `projects/16089620894539968109` ("Live Agent Business Assistant").

### 9.1 Extracted Dual-Theme Philosophy
- **Light Theme ("Warm Technical Dossier")**:
  - Page: `#F6F1E7`
  - Surfaces: `#FAF6EE` (base), `#FFFFFF` (lowest), `#F8F3E9` (low), `#F2EDE3` (container), `#EDE8DE` (high), `#E7E2D8` (highest)
  - Ink / Primary Text: `#181C22`, Muted Text: `#5A6578` (WCAG AAA / AA compliant)
  - Accent Color: Chartreuse / Lime `#84CC16`
  - Data / SQL Accent: Cyan `#0891B2`
  - Docs / RAG Accent: Amber `#B45309`
  - Success / Grounded: Emerald `#059669`

- **Dark Theme ("Modern HUD & Technical Brutalism")**:
  - Page: `#0E1116`
  - Surfaces: `#161B22` (base), `#0B0E13` (lowest), `#191C21` (low), `#1D242D` (container), `#272A30` (high), `#32353A` (highest)
  - Ink / Primary Text: `#F0F6FC`, Muted Text: `#8B949E`
  - Accent Color: Electric Lime `#C6F432` (`#C5F331`)
  - Data / SQL Accent: Bright Cyan `#22D3EE`
  - Docs / RAG Accent: Amber `#F59E0B`
  - Success / Grounded: Emerald `#10B981`

### 9.2 Typography Architecture (Google Fonts via `next/font/google`)
- **Headlines & Metric Display**: `Space Grotesk` (weights 600, 700) (`--font-headline`)
- **Body & Prose**: `IBM Plex Sans` (weights 400, 500, 600) (`--font-body`)
- **Telemetry, Code & Numbers**: `JetBrains Mono` (weights 400, 500, 700) (`--font-mono`)

### 9.3 Rebuilt Component Directory
- `Sidebar.jsx`: 72px fixed utility rail with geometric mark, vertical tab stack with notification badges, day/dark theme toggle, and live cluster latency indicator. Full mobile drawer overlay for `<1024px`.
- `StatTile.jsx`: Telemetry card with 600ms count-up, semantic icon badge, and accent left border.
- `StarterRow.jsx`: Inquiry card with 2px hover lift, route pill badge, and sliding arrow.
- `SegmentedControl.jsx`: Route selector with `framer-motion` sliding pill (`layoutId`).
- `Composer.jsx`: Raised card with auto-resizing textarea, shift+enter hint, and Electric Lime execute button.
- `ChatMessage.jsx`: User questions with `#QRY-01` badge and Space Grotesk headline; Assistant answers in left-lime border card with streaming cursor and citation chips.
- `EvidencePanel.jsx`: 420px desktop fixed panel and mobile bottom sheet featuring:
  - Vertical Inference Call Stack with traveling pulse animation.
  - Dark terminal SQL code block with execution time and copy button.
  - Tabular snippet with monospaced figures.
  - Vector chunk cards with similarity score bars.
  - Animated SVG Pipeline Topology Map with moving telemetry particles (`animateMotion`).
- `Timeline.jsx`: Multi-agent pipeline tracker supporting horizontal dispatch flow and vertical inference call stack.
- `DataQualityView.jsx`: Matches Stitch screen `d1f35...` with Global Health Index radial SVG ring (96%), delta convergence bars, Spark 3.5 engine profile, and automated schema invariant table.
- `SupportDeskView.jsx`, `TicketList.jsx`, `TicketDetail.jsx`: Matches Stitch screen `8c88...` with 4 KPI strips, backlog list, 7-step LangGraph node pipeline tracker, unified diff / SQL fix view, and HITL approval controls.
