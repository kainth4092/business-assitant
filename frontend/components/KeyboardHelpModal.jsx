"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";

const SHORTCUTS = [
  { keys: "⌘K / Ctrl+K", desc: "Open command palette (screens, tickets, docs, ask)" },
  { keys: "1 – 5", desc: "Switch between Analysis, Support, Quality, Docs, and Projects" },
  { keys: "N", desc: "Start a new analysis session" },
  { keys: "E", desc: "Toggle evidence margin notes" },
  { keys: "D", desc: "Toggle Day Paper / Night Shift theme" },
  { keys: "Enter", desc: "Dispatch query in Analysis composer" },
  { keys: "Shift+Enter", desc: "Insert newline in composer" },
  { keys: "Esc", desc: "Close active sheet, palette, or modal" },
  { keys: "?", desc: "Open or close this shortcuts reference" },
];

export default function KeyboardHelpModal({ isOpen = false, onClose = () => {} }) {
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/45"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xs border border-ink bg-raised paper-stack-strong overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-grid bg-sunken flex items-center justify-between">
          <h2 className="font-serif text-base font-semibold text-ink">
            Keyboard Shortcuts
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-xs border border-grid bg-raised text-muted hover:text-ink cursor-pointer"
            aria-label="Close shortcuts help"
          >
            <X className="w-4 h-4" strokeWidth={1.6} />
          </button>
        </div>

        <div className="divide-y divide-grid">
          {SHORTCUTS.map((s) => (
            <div
              key={s.keys}
              className="px-4 py-2.5 flex items-center justify-between gap-4 text-xs"
            >
              <span className="font-sans text-ink">{s.desc}</span>
              <kbd className="px-2 py-0.5 rounded-xs border border-grid bg-paper font-mono text-[11px] font-semibold text-ink shrink-0">
                {s.keys}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
