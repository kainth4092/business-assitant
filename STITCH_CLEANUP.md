# Stitch Cleanup Audit & Inventory (STITCH_CLEANUP.md)

This document catalogs all files, assets, scripts, and code references associated with the Stitch integration, along with the action taken for each item as part of Part 1 cleanup.

---

## 1. Files & Folders Removed

| Path | Reason for Removal |
| :--- | :--- |
| `DESIGN.md` | Stitch-generated design specifications, tokens, and Stitch component references. |
| `design/projects.json` | Exported Stitch project metadata from Google Cloud Stitch API. |
| `design/project_details.json` | Stitch project configuration details for "Live Agent Business Assistant". |
| `design/design_systems_list.json` | Stitch design system token catalog export. |
| `design/screens.json` | Exported list of generated Stitch screen IDs, URLs, and states. |
| `design/screens/39f5add39d8b4068af32ef0e90708a95_Business_Assistant_-_Live_Analysis_(Light_Theme).html` | Static HTML export of Stitch Live Analysis light theme mockup. |
| `design/screens/39f5add39d8b4068af32ef0e90708a95_detail.json` | Exported metadata for Stitch Live Analysis light theme screen. |
| `design/screens/870cc0451a1045908c13cd03ba90b760_Business_Assistant_-_Live_Analysis_(Light_Theme).html` | Static HTML export of Stitch Live Analysis light theme variant mockup. |
| `design/screens/870cc0451a1045908c13cd03ba90b760_detail.json` | Exported metadata for Stitch Live Analysis light theme variant. |
| `design/screens/8c88d588d29848c1ac9d623e4d9c347c_Business_Assistant_-_Support_Desk.html` | Static HTML export of Stitch Support Desk mockup. |
| `design/screens/8c88d588d29848c1ac9d623e4d9c347c_detail.json` | Exported metadata for Stitch Support Desk screen. |
| `design/screens/97a9442c557743ec93e21836ce0c7a39_Business_Assistant_-_Live_Analysis.html` | Static HTML export of Stitch Live Analysis dark theme mockup. |
| `design/screens/97a9442c557743ec93e21836ce0c7a39_detail.json` | Exported metadata for Stitch Live Analysis dark theme screen. |
| `design/screens/d1f350125a86484ca7b327253335b980_Business_Assistant_-_Data_Quality.html` | Static HTML export of Stitch Data Quality audit view mockup. |
| `design/screens/d1f350125a86484ca7b327253335b980_detail.json` | Exported metadata for Stitch Data Quality screen. |
| `design/screenshots/39f5add39d8b4068af32ef0e90708a95_Business_Assistant_-_Live_Analysis_(Light_Theme).png` | Rendered PNG screenshot of Stitch light theme screen. |
| `design/screenshots/870cc0451a1045908c13cd03ba90b760_Business_Assistant_-_Live_Analysis_(Light_Theme).png` | Rendered PNG screenshot of Stitch light theme variant screen. |
| `design/screenshots/8c88d588d29848c1ac9d623e4d9c347c_Business_Assistant_-_Support_Desk.png` | Rendered PNG screenshot of Stitch Support Desk screen. |
| `design/screenshots/97a9442c557743ec93e21836ce0c7a39_Business_Assistant_-_Live_Analysis.png` | Rendered PNG screenshot of Stitch dark theme screen. |
| `design/screenshots/d1f350125a86484ca7b327253335b980_Business_Assistant_-_Data_Quality.png` | Rendered PNG screenshot of Stitch Data Quality screen. |
| `scripts/fetch_stitch_assets.py` | Standalone utility script created exclusively to connect to the Stitch MCP server and download assets. |

---

## 2. In-Code References Cleaned

| Location | Original Reference | Cleaned Status |
| :--- | :--- | :--- |
| `frontend/app/page.jsx:401` | `{/* Sticky Top Header (Matches Stitch Spec) */}` | Changed to `{/* Sticky Top Header */}`. |
| `frontend/components/ChatMessage.jsx:25` | `// User Question Entry (Matches Stitch Spec: #QRY-01 badge, Space Grotesk 20px)` | Changed to `// User Question Entry`. |
| `frontend/components/Sidebar.jsx:65` | `{/* 1. DESKTOP 72px UTILITY RAIL (Matches Stitch Spec) */}` | Changed to `{/* 1. DESKTOP 72px UTILITY RAIL */}`. |
| `DESIGN_NOTES.md:143-189` | Section 9 "Stitch Design System Implementation" with Stitch workspace and screen ID references | Removed Stitch project IDs and screen IDs; retained neutral architectural component documentation. |
| `frontend/DESIGN_NOTES.md` | Duplicate Stitch redesign notes | Synchronized to remove Stitch references. |

---

## 3. Kept, Because It Is Still Used

The following items are shared with the active, working application and are **retained** to ensure 100% functionality and clean visual presentation:

| Item / File | Reason Kept |
| :--- | :--- |
| `frontend/components/ThemeToggle.jsx` | Actively imported by `frontend/components/Sidebar.jsx` to provide dark/light theme switching. |
| `frontend/components/DataQualityView.jsx` | Actively rendered by `frontend/app/page.jsx` for the Data Quality ETL audit view. |
| `frontend/components/SupportDeskView.jsx` | Actively rendered by `frontend/app/page.jsx` for Support Desk workflow. |
| `frontend/components/TicketList.jsx` | Actively imported by `SupportDeskView.jsx` to list customer tickets. |
| `frontend/components/TicketDetail.jsx` | Actively imported by `SupportDeskView.jsx` for ticket detail and HITL approval. |
| `frontend/components/DocumentsView.jsx` | Actively rendered by `frontend/app/page.jsx` for RAG document inspection. |
| `frontend/components/EvidencePanel.jsx` | Actively rendered by `frontend/app/page.jsx` to display live retrieval traces and SQL telemetry. |
| `frontend/components/DataTable.jsx` | Actively rendered in chat messages to display structured query results. |
| `frontend/components/SqlBlock.jsx` | Actively rendered to display sanitized, syntax-highlighted SQL. |
| `frontend/components/Composer.jsx` | Actively rendered for the chat input and routing controls. |
| `frontend/components/EmptyState.jsx` | Actively rendered when no chat messages exist. |
| `frontend/components/CitationChip.jsx` | Actively rendered for inline citations. |
| `frontend/components/SourceChip.jsx` | Actively rendered for document source chips. |
| `frontend/components/Timeline.jsx` | Actively rendered in evidence drawer for agent execution steps. |
| `frontend/components/QualityBars.jsx` | Actively rendered in data quality view for comparison metrics. |
| `frontend/components/StarterRow.jsx` | Actively rendered in empty state for starter queries. |
| `frontend/components/StatTile.jsx` | Actively rendered in empty state for summary counts. |
| `frontend/components/StatusLine.jsx` | Actively rendered during active query processing. |
| `frontend/components/SegmentedControl.jsx` | Actively rendered in composer for routing selection. |
| CSS Semantic Tokens in `globals.css` & `tailwind.config.js` | Neutral CSS tokens (`--bg-surface`, `--text-primary`, `--border-default`, `--accent-lime`, etc.) used across all components for clean contrast without external design system dependencies. |
