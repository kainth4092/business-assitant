# Design System Specification: Warm Technical Dossier & Modern HUD

Extracted directly from the Stitch project **"Live Agent Business Assistant"** (`projects/16089620894539968109`).

---

## 1. Design Philosophy & Aesthetic
The design system establishes a mission-critical, telemetry-driven operating environment for high-velocity operators and business intelligence analysts. It fuses the tactile warmth of archival stationery with the ruthless precision of aerospace telemetric consoles and high-frequency trading terminals.

- **Archival Tactility (Light Theme):** Natural warmth replacing sterile corporate white, mimicking archival bond paper, bespoke ledger books, and physical dossier folders (`#F6F1E7`).
- **Technical Brutalism (Dark Theme):** Pure opacity layers, crisp 1px hairline framing, deep technical slate (`#0E1116`), zero blurry frosted glass or faux-physical skeuomorphism.
- **Instrument Precision:** Crisp 1px structural framing, compact monospaced telemetry (`JetBrains Mono`), and high-density information layout.
- **Strict Semantic Attribution:** Color is never ornamental. Every hue represents a deterministic processing state:
  - **Electric Lime / Chartreuse (`#84CC16` / `#C6F432`):** Primary action, execution triggers, active agent work.
  - **Cyber Cyan (`#0891B2` / `#22D3EE`):** Structured SQL data, PostgreSQL queries, database schema.
  - **Archival Amber (`#B45309` / `#F59E0B`):** Document RAG, vector embeddings, policy citations.
  - **Emerald (`#059669` / `#10B981`):** Verified claims, groundedness checks, passing tests, continuous sync.
  - **Crimson (`#DC2626` / `#FFB4AB`):** Fatal errors, rejections, anomaly warnings.

---

## 2. Color Palette & Semantic Tokens

### Light Theme ("Warm Technical Dossier")
| Token | Variable | Value | Purpose |
| :--- | :--- | :--- | :--- |
| **Canvas / Page** | `--bg-page` | `#F6F1E7` | Baseline archival paper canvas |
| **Surface / Card** | `--bg-surface` | `#FAF6EE` | Primary card & workbench panels |
| **Surface Lowest** | `--bg-surface-lowest` | `#FFFFFF` | Input fields, active cards |
| **Surface Low** | `--bg-surface-low` | `#F8F3E9` | Raised sub-containers |
| **Surface Container**| `--bg-surface-container` | `#F2EDE3` | Segmented controls, status bars |
| **Surface High** | `--bg-surface-high` | `#EDE8DE` | Active item hover, modal headers |
| **Surface Highest** | `--bg-surface-highest` | `#E7E2D8` | Rail background, dividers |
| **Ink (Primary)** | `--text-primary` | `#181C22` | Bold titles, primary text |
| **Ink Muted** | `--text-muted` | `#5A6578` | Secondary labels, descriptions (WCAG AA > 5.5:1) |
| **Border Default** | `--border-default` | `#DFD5C4` | 1px perimeter framing |
| **Border Strong** | `--border-strong` | `#DCD3C4` | Focused states, active headers |
| **Primary Action** | `--accent-lime` | `#84CC16` | Execute action button, active timeline |
| **Data (SQL)** | `--accent-cyan` | `#0891B2` | SQL queries, tabular data chips |
| **Docs (RAG)** | `--accent-amber` | `#B45309` | Document sources, policy chips |
| **Success / Grounded**| `--accent-emerald` | `#059669` | Groundedness verified, passes |
| **Error / Alert** | `--accent-crimson` | `#DC2626` | Execution errors, critical warnings |

### Dark Theme ("Modern HUD & Technical Brutalism")
| Token | Variable | Value | Purpose |
| :--- | :--- | :--- | :--- |
| **Canvas / Page** | `--bg-page` | `#0E1116` | Baseline dark terminal canvas |
| **Surface / Card** | `--bg-surface` | `#161B22` | Primary panel & card background |
| **Surface Lowest** | `--bg-surface-lowest` | `#0B0E13` | Deepest inset panels |
| **Surface Low** | `--bg-surface-low` | `#191C21` | Sub-cards, input bays |
| **Surface Container**| `--bg-surface-container` | `#1D242D` | Timeline blocks, active inspect |
| **Surface High** | `--bg-surface-high` | `#272A30` | Hover states, card headers |
| **Surface Highest** | `--bg-surface-highest` | `#32353A` | Toolbars, segmented controls |
| **Ink (Primary)** | `--text-primary` | `#F0F6FC` | High-contrast terminal text |
| **Ink Muted** | `--text-muted` | `#8B949E` | Secondary telemetry text (WCAG AA > 6.5:1) |
| **Border Default** | `--border-default` | `#2A323C` | 1px perimeter lines |
| **Border Strong** | `--border-strong` | `#384454` | Active card borders, modal bounds |
| **Primary Action** | `--accent-lime` | `#C6F432` | High-vis Electric Lime button |
| **Data (SQL)** | `--accent-cyan` | `#22D3EE` | SQL queries, tabular data chips |
| **Docs (RAG)** | `--accent-amber` | `#F59E0B` | Document sources, policy chips |
| **Success / Grounded**| `--accent-emerald` | `#10B981` | Groundedness verified, passes |
| **Error / Alert** | `--accent-crimson` | `#FFB4AB` | Execution errors, critical warnings |

---

## 3. Typography & Hierarchy

Loaded via Google Fonts (`Space Grotesk`, `IBM Plex Sans`, `JetBrains Mono`):

| Token | Family | Size / Line-Height | Weight | Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`headline-xl`** | Space Grotesk | 32px / 40px | 700 | -0.02em | Hero headers, view titles |
| **`headline-lg`** | Space Grotesk | 24px / 28px | 600 | -0.015em | Section titles, drawer titles |
| **`headline-md`** | Space Grotesk | 18px / 24px | 600 | -0.01em | Card headers, starter questions |
| **`body-lg`** | IBM Plex Sans | 16px / 24px | 400 | normal | Main prose answers, documentation |
| **`body-md`** | IBM Plex Sans | 14px / 20px | 400 / 500 | normal | Default UI text, inputs, messages |
| **`body-sm`** | IBM Plex Sans | 12px / 16px | 400 / 500 | normal | Captions, hints, footnotes |
| **`metric-display`**| JetBrains Mono | 28px / 32px | 700 | -0.03em | Primary KPI counters, big numbers |
| **`label-telemetry`**| JetBrains Mono | 11px / 14px | 500 / 600 | 0.06em | Status pills, badge labels, route tags |
| **`code-md`** | JetBrains Mono | 12px / 18px | 500 | normal | SQL blocks, diff blocks, latency |

---

## 4. Layout Architecture & Grid

- **Fixed Utility Rail (Left Navigation):** `72px` fixed width on desktop, collapsing to an overlay drawer on mobile (<1024px). Houses the logo, icon-centric view buttons, day/dark theme toggle, and live telemetry heartbeat.
- **Top Sticky Header:** `h-16` (64px) sticky navigation bar with breadcrumb path (`Business Assistant / Live Analysis #RUN-8842`), live agent working indicator with pulsing pip, and quick action controls.
- **Main Operational Canvas:** Fluid container (`pl-[72px] xl:pr-[400px]`), max-w-4xl for comfortable prose reading, scaling cleanly down to 390px mobile screens.
- **Evidence & Telemetry Inspector (Right Aside):** `400px` fixed panel on desktop (≥ 1280px), slide-over sheet on tablet (640-1279px), and bottom drawer on mobile (<640px). Displays real-time agent call stack, syntax-highlighted SQL with copy button, query results table, and retrieved markdown citations.

---

## 5. Motion & Micro-Interactions Spec

Implemented via CSS transitions and **`framer-motion`**:
1. **Active Working Status Dot:** Pulse ring (1.6s loop) running strictly while `isLoading === true`. Neutral static dot when idle.
2. **Step Tracker Nodes:** 5 horizontal nodes (`1. Route` -> `2. SQL Gen` -> `3. Retrieve` -> `4. Synthesis` -> `5. Safety`) filling sequentially with active pulse on the working step.
3. **Execution Timeline Connector:** Vertical line fills progressively as nodes complete, with a pulsing beam travelling between active nodes.
4. **Streaming Typewriter Effect:** Assistant answers stream in progressively with a blinking monospaced cursor `|`.
5. **Telemetry Counter Count-Up:** Number counters (sales rows, chunks, tools) animate from 0 to target over 600ms on mount.
6. **Sliding Segmented Control Pill:** The route selector (`Auto`, `Data`, `Docs`, `Both`) features a sliding spring pill under the active button (`layoutId="activePill"`).
7. **Starter Card Hover Lift:** 2px physical lift (`-translate-y-0.5`) with the right arrow sliding in (`translate-x-1`).
8. **Toast Notifications:** Slide-in from top-right with 250ms spring entrance and auto-dismiss.
9. **Accessibility:** All animations respect `@media (prefers-reduced-motion: reduce)`.
