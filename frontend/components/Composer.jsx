"use client";

import React, { useRef, useEffect } from "react";
import { ArrowUp, CornerDownLeft } from "lucide-react";
import SegmentedControl from "./SegmentedControl";

export default function Composer({
  inputQuery = "",
  onInputChange = () => {},
  onSubmit = () => {},
  isLoading = false,
  selectedRoute = "auto",
  onRouteChange = () => {},
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [inputQuery]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div
      className="sticky bottom-0 pt-3 pb-3 bg-page z-30 transition-colors"
      style={{ backgroundColor: "var(--bg-page)" }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="rounded-lg border border-border bg-surface shadow-composer focus-within:border-border-strong focus-within:ring-1 focus-within:ring-accent-lime/30 transition-all"
      >
        {/* Top Control Bar */}
        <div className="px-3 py-2 border-b border-border bg-surface-low flex items-center justify-between rounded-t-lg">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase text-muted font-bold tracking-wider hidden sm:inline">
              ROUTING:
            </span>
            <SegmentedControl
              selectedRoute={selectedRoute}
              onChange={onRouteChange}
            />
          </div>

          <span className="font-mono text-[11px] text-muted hidden md:inline font-medium">
            Shift + Enter for newline
          </span>
        </div>

        {/* Textarea Input */}
        <div className="px-3.5 pt-3 pb-2">
          <textarea
            ref={textareaRef}
            value={inputQuery}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about sales revenue, store performance, or return & promotion policies..."
            rows={1}
            disabled={isLoading}
            className="w-full bg-transparent text-body-md text-primary placeholder:text-muted resize-none focus:outline-none min-h-[44px] max-h-44 leading-relaxed font-body"
          />
        </div>

        {/* Footer Actions */}
        <div className="px-3.5 py-2.5 border-t border-border bg-surface flex items-center justify-between rounded-b-lg">
          <div className="flex items-center gap-2 text-muted font-mono text-[11px] font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald inline-block" />
            <span>PostgreSQL 16 &middot; pgvector HNSW</span>
          </div>

          <button
            type="submit"
            disabled={isLoading || !inputQuery.trim()}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-bold font-headline rounded bg-accent-lime hover:bg-accent-lime-hover text-accent-lime-contrast disabled:opacity-40 disabled:cursor-not-allowed shadow-xs active:scale-95 transition-all"
            aria-label="Execute analysis"
          >
            <span>Run Analysis</span>
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </form>
    </div>
  );
}
