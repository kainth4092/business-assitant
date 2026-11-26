# Design System & Architecture Notes: Business Assistant

## 1. Design Concept: Japanese Stationery × Air-Traffic-Control Flight Strips

Business Assistant is a dense, keyboard-first AI operations control room designed for data analysts, engineers, and engineering managers who work in the tool all day.

It deliberately combines two physical reference worlds:
1. **Stationery world (MUJI / Hobonichi notebooks)**: warm matte paper (`#F3EFE4`), raised ivory sheet (`#FBF9F2`), recessed ledger wells (`#E8E2D2`), subtle 4% opacity ruled grid paper (`24px` square grid), ink (`#16202F`), muted ink (`#55524A`), red hanko seal stamps (`#C8372D`), and yellow highlighter marker strokes (`#F2D45C`).
2. **Flight-strip world**: every support ticket and agent execution is treated as a physical strip on a control board with fixed fields (`ID`, `channel`, `sender`, `category`, `state`, `age`), monospaced callsigns, crisp `1px` hairline borders, `2px` max corners, hard offset paper-stack shadows (`2px 2px 0`), and rotated seal stamps (`APPROVED`, `REJECTED`, `NEEDS REVIEW`, `APPLIED`, `FLAGGED`).

### Hard Prohibitions
- No purple/pink gradients or gradient text.
- No glassmorphism, backdrop blur, glowing orbs, sparkle icons, or emojis.
- No soft blurred card shadows or `rounded-xl` / `rounded-2xl` containers.
- No Inter or Arial visual identity; no marketing hero copy.

---

## 2. Color Tokens (CSS Custom Properties)

Defined in [globals.css](file:///home/kanish/Documents/business-assistant/frontend/app/globals.css) and mapped in [tailwind.config.js](file:///home/kanish/Documents/business-assistant/frontend/tailwind.config.js).

| Token | Light ("Stationery Day Shift") | Dark ("Night Shift") | Role |
| :--- | :--- | :--- | :--- |
| `--bg-paper` | `#F3EFE4` | `#10151D` | Main grid-paper canvas |
| `--bg-raised` | `#FBF9F2` | `#171E29` | Raised sheets, strips, spine, margin |
| `--bg-sunken` | `#E8E2D2` | `#0B0F15` | Wells, table headers, board bays |
| `--grid-line` | `#D3CCB9` | `#283344` | 1px hairline borders & offset stack shadow |
| `--ink` | `#16202F` | `#E9E4D6` | Primary text & ink actions |
| `--muted` | `#55524A` | `#A9A292` | Secondary labels (>= 4.5:1 AA contrast) |
| `--seal-red` | `#C8372D` | `#D6493E` | Hanko seal stamps, approvals, destructive actions |
| `--highlighter` | `#F2D45C` | `#E6C74C` | Active step stroke & selected marker highlight |
| `--sage` | `#5E8C6A` | `#6CA27A` | Success / groundedness / BOTH route |
| `--amber` | `#B7791F` | `#D99B38` | Warning / review state |
| `--route-data` | `#2F5D8A` | `#5D96CC` | DATA (SQL) route accent (paired with text label) |
| `--route-docs` | `#A8741A` | `#D99B38` | DOCS (RAG) route accent (paired with text label) |
| `--route-both` | `#5E8C6A` | `#6CA27A` | BOTH (SQL + DOCS) route accent (paired with text label) |

All foreground text uses `color-mix(in srgb, <accent> 64-88%, var(--ink))` (`--*-ink` tokens) on light paper so small text strictly clears WCAG AA 4.5:1 contrast while preserving the exact palette hue on borders, rules, and bars.

---

## 3. Typography & Type Scale

Loaded locally via `next/font/google` in [layout.jsx](file:///home/kanish/Documents/business-assistant/frontend/app/layout.jsx) with system fallback stacks:
- **Headings & Serif Log Answers (`--font-serif`)**: `Shippori Mincho` (weights `400–800`), fallback `"Hiragino Mincho ProN", Georgia, serif`.
  - Page title: `24px–30px` (`text-2xl sm:text-3xl font-semibold`)
  - Log entry / question heading: `18px–20px` (`text-lg sm:text-xl font-semibold`)
  - Answer prose: `15.5px / 1.7` line-height
- **UI Body (`--font-sans`)**: `Zen Kaku Gothic New` (weights `400, 500, 700`), fallback `"Hiragino Sans", system-ui, sans-serif`.
  - Standard UI controls, descriptions, and summaries: `12px–14px`
- **IDs, SQL, Numbers, Tags & Timestamps (`--font-mono`)**: `JetBrains Mono` (weights `400–700`) with `font-variant-numeric: tabular-nums`.
  - Metrics: `20px–30px` (`text-xl sm:text-3xl font-bold tabular-mono`)
  - Field labels & stamps: `10px–11px` uppercase (`tracking-wider`)
  - SQL & diffs: `11.5px–12px`

---

## 4. Spacing, Geometry & Layout Rules

- **Base Grid**: `8px` rhythm (`4px` / `8px` / `12px` / `16px` / `20px` increments) with a `24px × 24px` CSS grid-paper background at ~4% ink opacity.
- **Corners & Borders**: `2px` maximum border radius (`rounded-xs`), `1px` hairline borders (`border-grid`), and hard offset depth (`2px 2px 0 var(--grid-line)`).
- **Asymmetric Workbench Grid**:
  - `>= 1280px`: `188px` narrow left `Spine` + wide fluid main logbook column + `392px` right `Margin` notes column.
  - `768px – 1279px`: `188px` left `Spine` + fluid main column; `Margin` opens as a right drawer.
  - `390px` mobile: fixed bottom navigation bar (`56px`) + slide-over drawer; `Margin` opens as an `84vh` bottom sheet.
- **Modern Platform CSS**: CSS container queries (`.board-container`, `.catalog-container`), `:has()` focus styling on `.composer-frame` and `.strip-card`, `document.startViewTransition` for screen switches, `color-mix()`, and logical properties (`border-inline-start`, `padding-inline`).

---

## 5. Component Inventory

| Component | File | Purpose |
| :--- | :--- | :--- |
| `WorkbenchApp` | `frontend/components/WorkbenchApp.jsx` | Client shell, global shortcuts (`⌘K`, `?`, `1–4`, `N`, `E`, `D`), SSE orchestration |
| `Spine` | `frontend/components/Spine.jsx` | Narrow left navigation spine, session logbook, mobile bottom bar & drawer |
| `LogEntry` | `frontend/components/LogEntry.jsx` | Ruled-line question entry + Shippori Mincho answer with interactive `[n]` citations |
| `Margin` | `frontend/components/Margin.jsx` | Right margin notes column / mobile bottom sheet for evidence & traces |
| `Timeline` | `frontend/components/Timeline.jsx` | 5-step execution stack (`Route`, `Query`, `Retrieve`, `Answer`, `Check`) |
| `SqlBlock` | `frontend/components/SqlBlock.jsx` | High-contrast read-only SQL block with copy feedback |
| `DataTable` | `frontend/components/DataTable.jsx` | Ruled table with right-aligned tabular numbers |
| `Composer` | `frontend/components/Composer.jsx` | Sticky ledger composer with `Shift+Enter` and route tab index |
| `SegmentedControl` | `frontend/components/SegmentedControl.jsx` | Stationery tab index for `Auto`, `Data`, `Docs`, `Both` |
| `StripBoard` | `frontend/components/StripBoard.jsx` | 5-column ATC flight-strip board (`New`, `Investigating`, `Fix ready`, `Applied`, `Rejected`) |
| `Strip` | `frontend/components/Strip.jsx` | Individual horizontal flight strip with fixed fields |
| `TicketDetail` | `frontend/components/TicketDetail.jsx` | Inspection sheet with escaped message, diff, sandbox before/after, two-step approval |
| `Stamp` | `frontend/components/Stamp.jsx` | Rotated square/circle hanko seal marks (`APPROVED`, `REJECTED`, `NEEDS REVIEW`, etc.) |
| `ChannelStatus` | `frontend/components/ChannelStatus.jsx` | Live Slack, Email, and Teams status with toggle switches |
| `DataQualityView` | `frontend/components/DataQualityView.jsx` | Plain-language summary, mono counters, ruled bars, and issue table |
| `QualityBars` | `frontend/components/QualityBars.jsx` | Before/after ruled progress bars with large tabular figures |
| `DocumentsView` | `frontend/components/DocumentsView.jsx` | Card catalog grid, upload, search, and chunk inspector |
| `IndexCard` | `frontend/components/IndexCard.jsx` | Stationery catalog card for an indexed document |
| `CommandPalette` | `frontend/components/CommandPalette.jsx` | `Ctrl+K` / `Cmd+K` keyboard switcher across screens, tickets, docs, and queries |
| `KeyboardHelpModal` | `frontend/components/KeyboardHelpModal.jsx` | `?` keyboard shortcuts reference sheet |
| `EmptyState` | `frontend/components/EmptyState.jsx` | 3-step first-run onboarding checklist + live schema starter questions |
| `AddDataArea` / `AddDataModal` | `frontend/components/AddDataArea.jsx` | CSV & document upload and PySpark pipeline runner |
| `ErrorState` | `frontend/components/ErrorState.jsx` | Specific error banner with retry action |
| `Skeleton` | `frontend/components/Skeleton.jsx` | Paper-sweep loading placeholders for strips and tables |
| `ThemeToggle` | `frontend/components/ThemeToggle.jsx` | Day Paper / Night Shift switcher |

---

## 6. Motion Rules

All animations respect `prefers-reduced-motion: reduce`:
- **Seal Stamp (`stamp-drop`)**: `180ms` scale (`1.32 → 0.96 → 1`) and settle at `-1.5deg` on approval or rejection.
- **New Flight Strip (`strip-slide-in`)**: `200ms` slide from right (`18px → 0`) with a highlighter wash that fades to paper surface.
- **Working Indicator (`highlighter-sweep`)**: Active timeline step draws a highlighter stroke left-to-right while the `aria-live="polite"` status region names the active step. No bouncing dots or spinner-only loading.
- **Counters (`useCountUpOnce`)**: Numeric counters animate once over `500ms` on mount.
- **Hover**: Flight strips and index cards lift by `1px` (`-translate-y-px`).
- **View Transitions**: Screen switches use `document.startViewTransition` (`140ms` cross-fade) when supported and motion is allowed.

---

## 7. How to Extend the Design

1. **Adding a new screen**: Add a tab entry in `Spine.jsx` with a two-digit callsign (`05`), wire the shortcut in `WorkbenchApp.jsx`, add an entry in `CommandPalette.jsx`, and wrap the view in `max-w-6xl mx-auto` with `ErrorState`, `Skeleton`, and empty state coverage.
2. **Adding a new status stamp**: Add an entry to `STAMP_MAP` in `Stamp.jsx` using existing CSS variables (`--seal-red`, `--sage`, `--amber`, `--route-data`) and always pair color with explicit uppercase text.
3. **Adding a new token**: Define both `:root` and `.dark` values in `frontend/app/globals.css`, map the utility in `frontend/tailwind.config.js`, and verify >= 4.5:1 contrast with `axe-core`.
