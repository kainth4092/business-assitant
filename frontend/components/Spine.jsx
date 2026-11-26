"use client";

import React from "react";
import {
  FileSpreadsheet,
  LifeBuoy,
  CheckSquare,
  BookOpen,
  FolderGit2,
  Plus,
  Search,
  HelpCircle,
  X,
  History,
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";

export default function Spine({
  activeTab = "chat",
  onSelectTab = () => {},
  onNewSession = () => {},
  history = [],
  activeQuestionId = null,
  onSelectHistory = () => {},
  systemHealth = null,
  pendingTicketsCount = 0,
  isMobileOpen = false,
  onCloseMobile = () => {},
  onOpenCommandPalette = () => {},
  onOpenKeyboardHelp = () => {},
}) {
  const tabs = [
    {
      id: "chat",
      code: "01",
      label: "Analysis",
      icon: FileSpreadsheet,
      count: history.length > 0 ? history.length : null,
      urgent: false,
    },
    {
      id: "support-desk",
      code: "02",
      label: "Support",
      icon: LifeBuoy,
      count: pendingTicketsCount > 0 ? pendingTicketsCount : null,
      urgent: pendingTicketsCount > 0,
    },
    {
      id: "data-quality",
      code: "03",
      label: "Quality",
      icon: CheckSquare,
      count: null,
      urgent: false,
    },
    {
      id: "documents",
      code: "04",
      label: "Docs",
      icon: BookOpen,
      count:
        systemHealth?.indexed_chunks > 0 ? systemHealth.indexed_chunks : null,
      urgent: false,
    },
    {
      id: "projects",
      code: "05",
      label: "Projects",
      icon: FolderGit2,
      count: null,
      urgent: false,
    },
  ];

  const handleTabClick = (tabId) => {
    if (activeTab === tabId && tabId === "chat") {
      onNewSession();
    } else {
      onSelectTab(tabId);
    }
  };

  const renderSpineContent = (isDrawer = false) => (
    <div className="flex flex-col h-full justify-between">
      <div>
        {/* Brand Stamp / Callsign */}
        <div className="px-3 py-3 border-b border-grid flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              onSelectTab("chat");
              onNewSession();
              if (isDrawer) onCloseMobile();
            }}
            className="flex items-center gap-2 text-left cursor-pointer group"
          >
            <span className="w-7 h-7 rounded-xs border-[1.5px] border-seal bg-seal-tint flex items-center justify-center font-mono text-[10px] font-bold text-seal-ink -rotate-2 shrink-0">
              BA
            </span>
            <div className="min-w-0">
              <div className="font-serif text-sm font-bold text-ink leading-none">
                Control Log
              </div>
              <div className="font-mono text-[9.5px] uppercase tracking-wider text-muted mt-0.5">
                Ops Workbench
              </div>
            </div>
          </button>

          {isDrawer && (
            <button
              type="button"
              onClick={onCloseMobile}
              className="p-1 rounded-xs border border-grid text-muted hover:text-ink cursor-pointer"
              aria-label="Close navigation drawer"
            >
              <X className="w-4 h-4" strokeWidth={1.6} />
            </button>
          )}
        </div>

        {/* New Query + Command Palette Trigger */}
        <div className="p-2.5 border-b border-grid space-y-1.5">
          <button
            type="button"
            onClick={() => {
              onSelectTab("chat");
              onNewSession();
              if (isDrawer) onCloseMobile();
            }}
            className="w-full inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-[11px] font-bold uppercase tracking-wider hover:opacity-90 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span>New Query</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (isDrawer) onCloseMobile();
              onOpenCommandPalette();
            }}
            className="w-full inline-flex items-center justify-between gap-1.5 px-2.5 py-1 rounded-xs border border-grid bg-paper text-muted hover:text-ink hover:border-grid-strong font-mono text-[11px] cursor-pointer"
          >
            <span className="inline-flex items-center gap-1.5">
              <Search className="w-3 h-3" strokeWidth={1.6} />
              <span>Command</span>
            </span>
            <kbd className="px-1 py-0 rounded-xs border border-grid bg-raised text-[9.5px] text-ink">
              ⌘K
            </kbd>
          </button>
        </div>

        {/* Primary Screen Navigation */}
        <nav aria-label="Primary workbench views" className="p-2 space-y-1 border-b border-grid">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                id={isDrawer ? undefined : `sidebar-tab-${tab.id}`}
                data-testid={isDrawer ? undefined : `sidebar-tab-${tab.id}`}
                aria-current={isActive ? "page" : undefined}
                onClick={() => {
                  handleTabClick(tab.id);
                  if (isDrawer) onCloseMobile();
                }}
                className={`w-full flex items-center justify-between gap-2 px-2.5 py-2 rounded-xs font-mono text-xs transition-colors cursor-pointer ${
                  isActive
                    ? "bg-highlighter-wash text-ink font-bold border border-ink"
                    : "text-muted hover:text-ink hover:bg-sunken/70 border border-transparent"
                }`}
              >
                <span className="flex items-center gap-2 min-w-0">
                  <span
                    className={`text-[10px] tabular-mono shrink-0 ${
                      isActive ? "text-ink" : "text-muted"
                    }`}
                  >
                    {tab.code}
                  </span>
                  <Icon className="w-3.5 h-3.5 shrink-0" strokeWidth={1.6} />
                  <span className="truncate">{tab.label}</span>
                </span>

                {tab.count !== null && (
                  <span
                    className={`px-1.5 py-0.2 rounded-xs font-mono text-[10px] font-bold tabular-mono shrink-0 ${
                      tab.urgent
                        ? "bg-seal text-seal-on"
                        : "border border-grid bg-raised text-ink"
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Session Log */}
        <div className="p-2 space-y-1">
          <div className="px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-muted font-bold flex items-center justify-between">
            <span className="inline-flex items-center gap-1">
              <History className="w-3 h-3" strokeWidth={1.6} />
              <span>Logbook</span>
            </span>
            <span className="tabular-mono">{history.length}</span>
          </div>

          <div className="space-y-1 max-h-56 overflow-y-auto pr-0.5">
            {history.length === 0 ? (
              <div className="px-2 py-3 font-mono text-[10.5px] text-muted">
                No entries recorded.
              </div>
            ) : (
              history.slice(0, 12).map((item) => {
                const selected = activeQuestionId === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      onSelectTab("chat");
                      onSelectHistory(item.id);
                      if (isDrawer) onCloseMobile();
                    }}
                    className={`w-full text-left px-2 py-1.5 rounded-xs border font-mono text-[11px] cursor-pointer transition-colors ${
                      selected
                        ? "border-ink bg-raised text-ink font-semibold"
                        : "border-transparent text-muted hover:text-ink hover:bg-sunken/60"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 text-[9.5px]">
                      <span className="font-bold text-route-data-ink">{item.tag}</span>
                      <span className="tabular-mono">{item.timestamp}</span>
                    </div>
                    <div className="font-sans text-[11.5px] text-ink line-clamp-1 mt-0.5">
                      {item.query}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Spine Footer: Theme, Shortcuts, DB Telemetry */}
      <div className="p-2.5 border-t border-grid space-y-2 bg-sunken/50">
        <div className="flex items-center gap-1.5">
          <ThemeToggle showLabel className="flex-1 justify-start" />
          <button
            type="button"
            onClick={() => {
              if (isDrawer) onCloseMobile();
              onOpenKeyboardHelp();
            }}
            className="h-8 w-8 rounded-xs border border-grid bg-raised text-muted hover:text-ink flex items-center justify-center cursor-pointer shrink-0"
            aria-label="Keyboard shortcuts"
            title="Keyboard shortcuts (?)"
          >
            <HelpCircle className="w-3.5 h-3.5" strokeWidth={1.6} />
          </button>
        </div>

        <div className="flex items-center justify-between font-mono text-[10px] text-muted px-0.5">
          <span className="inline-flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-xs"
              style={{
                backgroundColor:
                  systemHealth?.status === "healthy"
                    ? "var(--sage)"
                    : systemHealth?.status === "degraded"
                    ? "var(--amber)"
                    : "var(--seal-red)",
              }}
            />
            <span>
              {systemHealth?.status === "healthy"
                ? "PG ONLINE"
                : systemHealth?.status === "degraded"
                ? "DEGRADED"
                : "OFFLINE"}
            </span>
          </span>
          <span className="tabular-mono">
            {systemHealth?.sales_records !== undefined
              ? `${Number(systemHealth.sales_records).toLocaleString()} rows`
              : "—"}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop & Tablet Narrow Left Spine (md: 768px+) */}
      <aside
        aria-label="Workbench navigation spine"
        className="fixed left-0 top-0 bottom-0 w-[188px] bg-raised border-r border-grid z-30 hidden md:flex flex-col"
      >
        {renderSpineContent(false)}
      </aside>

      {/* Mobile Bottom Navigation Bar (<768px, e.g. 390px) */}
      <nav
        aria-label="Mobile navigation bar"
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-raised border-t border-grid grid grid-cols-5 h-14"
      >
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleTabClick(tab.id)}
              aria-current={isActive ? "page" : undefined}
              className={`relative flex flex-col items-center justify-center gap-0.5 font-mono text-[10px] cursor-pointer ${
                isActive ? "bg-highlighter-wash text-ink font-bold" : "text-muted"
              }`}
            >
              <Icon className="w-4 h-4" strokeWidth={1.6} />
              <span>{tab.label}</span>
              {tab.count !== null && (
                <span
                  className={`absolute top-1 right-2 px-1 rounded-xs text-[9px] font-bold tabular-mono ${
                    tab.urgent ? "bg-seal text-seal-on" : "bg-sunken text-ink border border-grid"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Mobile Slide-Over Drawer */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden bg-ink/45"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation drawer"
          onClick={onCloseMobile}
        >
          <aside
            className="w-72 h-full bg-raised border-r border-grid"
            onClick={(e) => e.stopPropagation()}
          >
            {renderSpineContent(true)}
          </aside>
        </div>
      )}
    </>
  );
}
