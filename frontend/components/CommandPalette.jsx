"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  FileSpreadsheet,
  LifeBuoy,
  CheckSquare,
  BookOpen,
  FolderGit2,
  Plus,
  Upload,
  Moon,
  HelpCircle,
  ArrowRight,
  PanelRightOpen,
} from "lucide-react";

function CommandPaletteDialog({
  onClose = () => {},
  onSelectTab = () => {},
  onNewSession = () => {},
  onOpenAddData = () => {},
  onToggleEvidence = () => {},
  onToggleTheme = () => {},
  onOpenHelp = () => {},
  onDispatchQuery = () => {},
  tickets = [],
  documents = [],
  onOpenTicket = () => {},
  onOpenDocument = () => {},
}) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 10);
    return () => clearTimeout(t);
  }, []);

  const baseItems = [
    {
      id: "nav-chat",
      group: "Screens",
      label: "Go to Analysis Logbook",
      shortcut: "1",
      icon: FileSpreadsheet,
      action: () => onSelectTab("chat"),
    },
    {
      id: "nav-support",
      group: "Screens",
      label: "Go to Support Desk Flight Strips",
      shortcut: "2",
      icon: LifeBuoy,
      action: () => onSelectTab("support-desk"),
    },
    {
      id: "nav-quality",
      group: "Screens",
      label: "Go to Data Quality Report",
      shortcut: "3",
      icon: CheckSquare,
      action: () => onSelectTab("data-quality"),
    },
    {
      id: "nav-docs",
      group: "Screens",
      label: "Go to Documents Catalog",
      shortcut: "4",
      icon: BookOpen,
      action: () => onSelectTab("documents"),
    },
    {
      id: "nav-projects",
      group: "Screens",
      label: "Go to Codebase Projects Registry",
      shortcut: "5",
      icon: FolderGit2,
      action: () => onSelectTab("projects"),
    },
    {
      id: "act-new",
      group: "Actions",
      label: "Start New Analysis Session",
      shortcut: "N",
      icon: Plus,
      action: () => {
        onSelectTab("chat");
        onNewSession();
      },
    },
    {
      id: "act-upload",
      group: "Actions",
      label: "Upload CSV or Policy Documents",
      shortcut: "U",
      icon: Upload,
      action: () => onOpenAddData(),
    },
    {
      id: "act-margin",
      group: "Actions",
      label: "Toggle Evidence Margin Notes",
      shortcut: "E",
      icon: PanelRightOpen,
      action: () => {
        onSelectTab("chat");
        onToggleEvidence();
      },
    },
    {
      id: "act-theme",
      group: "Actions",
      label: "Toggle Day Paper / Night Shift Theme",
      shortcut: "D",
      icon: Moon,
      action: () => onToggleTheme(),
    },
    {
      id: "act-help",
      group: "Actions",
      label: "Show Keyboard Shortcuts",
      shortcut: "?",
      icon: HelpCircle,
      action: () => onOpenHelp(),
    },
  ];

  const ticketItems = (tickets || []).slice(0, 12).map((t) => ({
    id: `ticket-${t.id}`,
    group: "Tickets",
    label: `#${t.id} · ${(t.message || t.title || "").slice(0, 64)}`,
    shortcut: String(t.status || "").toUpperCase(),
    icon: LifeBuoy,
    action: () => onOpenTicket(t.id),
  }));

  const docItems = (documents || []).slice(0, 12).map((d) => ({
    id: `doc-${d.source_file}`,
    group: "Documents",
    label: `${d.sample_title || d.source_file} (${d.source_file})`,
    shortcut: `${d.total_chunks} CHUNKS`,
    icon: BookOpen,
    action: () => onOpenDocument(d.source_file),
  }));

  const allItems = [...baseItems, ...ticketItems, ...docItems];
  const term = query.trim().toLowerCase();
  const filtered = term
    ? allItems.filter(
        (item) =>
          item.label.toLowerCase().includes(term) ||
          item.group.toLowerCase().includes(term)
      )
    : allItems;

  const finalItems =
    term.length >= 3
      ? [
          {
            id: "ask-direct",
            group: "Query",
            label: `Ask Analysis: "${query.trim()}"`,
            shortcut: "ENTER",
            icon: ArrowRight,
            action: () => onDispatchQuery(query.trim()),
          },
          ...filtered,
        ]
      : filtered;

  const clampedIdx = Math.min(activeIndex, Math.max(0, finalItems.length - 1));

  const runItem = (item) => {
    if (!item) return;
    onClose();
    item.action();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, finalItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      runItem(finalItems[clampedIdx]);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 p-4 bg-ink/45"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-xs border border-ink bg-raised paper-stack-strong overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="px-3.5 py-2.5 border-b border-grid bg-sunken flex items-center gap-2.5">
          <Search className="w-4 h-4 text-ink shrink-0" strokeWidth={1.6} />
          <label htmlFor="command-palette-input" className="sr-only">
            Type a command, ticket ID, document, or question
          </label>
          <input
            id="command-palette-input"
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            placeholder="Jump to screen, open ticket, inspect document, or ask a question..."
            className="w-full bg-transparent text-sm text-ink placeholder:text-muted font-sans focus:outline-none"
          />
          <kbd className="px-1.5 py-0.5 rounded-xs border border-grid bg-raised font-mono text-[10px] text-muted shrink-0">
            ESC
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto divide-y divide-grid/60">
          {finalItems.length === 0 ? (
            <div className="p-6 text-center font-mono text-xs text-muted">
              No matching commands or records.
            </div>
          ) : (
            finalItems.map((item, idx) => {
              const Icon = item.icon;
              const active = idx === clampedIdx;
              return (
                <button
                  key={item.id}
                  type="button"
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => runItem(item)}
                  className={`w-full text-left px-3.5 py-2.5 flex items-center justify-between gap-3 cursor-pointer transition-colors ${
                    active ? "bg-highlighter-wash text-ink" : "bg-raised text-ink"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className={`w-3.5 h-3.5 shrink-0 ${active ? "text-ink" : "text-muted"}`}
                      strokeWidth={1.6}
                    />
                    <span
                      className={`font-mono text-[10px] uppercase tracking-wider w-16 shrink-0 ${
                        active ? "text-ink font-bold" : "text-muted"
                      }`}
                    >
                      {item.group}
                    </span>
                    <span className="font-sans text-xs font-medium truncate">
                      {item.label}
                    </span>
                  </div>
                  {item.shortcut && (
                    <kbd className="px-1.5 py-0.5 rounded-xs border border-grid bg-paper font-mono text-[10px] text-muted shrink-0">
                      {item.shortcut}
                    </kbd>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default function CommandPalette(props) {
  if (!props.isOpen) return null;
  return <CommandPaletteDialog {...props} />;
}
