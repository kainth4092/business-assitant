"use client";

import React, { useRef, useEffect } from "react";
import { CornerDownLeft, ArrowUp } from "lucide-react";
import SegmentedControl from "./SegmentedControl";

export default function Composer({
  inputQuery = "",
  onInputChange = () => {},
  onSubmit = () => {},
  isLoading = false,
  selectedRoute = "auto",
  onRouteChange = () => {},
  composerRef = null,
}) {
  const localRef = useRef(null);
  const textareaRef = composerRef || localRef;

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [inputQuery, textareaRef]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="sticky bottom-0 z-20 pt-2 pb-3 bg-paper/95 border-t border-grid/60">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="composer-frame rounded-xs border border-grid bg-raised paper-stack transition-colors"
      >
        {/* Stationery Tab Index Header */}
        <div className="px-3 py-1.5 border-b border-grid bg-sunken/70 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted font-bold">
              Route
            </span>
            <SegmentedControl
              selectedRoute={selectedRoute}
              onChange={onRouteChange}
            />
          </div>

          <span className="font-mono text-[10.5px] text-muted hidden sm:inline">
            Enter to dispatch · Shift+Enter for newline
          </span>
        </div>

        {/* Ruled Entry Input */}
        <div className="px-3.5 py-2.5">
          <label htmlFor="analysis-query-input" className="sr-only">
            Ask a plain-English question over data and documents
          </label>
          <textarea
            id="analysis-query-input"
            ref={textareaRef}
            value={inputQuery}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write a plain-English question for SQL telemetry or policy documents..."
            rows={1}
            disabled={isLoading}
            className="w-full bg-transparent text-sm text-ink placeholder:text-muted resize-none focus:outline-none min-h-[38px] max-h-42 leading-relaxed font-sans"
          />
        </div>

        {/* Footer Dispatch Row */}
        <div className="px-3.5 py-2 border-t border-grid flex items-center justify-between gap-2 bg-raised">
          <div className="flex items-center gap-2 font-mono text-[10.5px] text-muted min-w-0 truncate">
            <span
              className="w-2 h-2 rounded-xs shrink-0"
              style={{ backgroundColor: "var(--sage)" }}
            />
            <span className="truncate">Read-only SQL &amp; pgvector RAG</span>
          </div>

          <button
            type="submit"
            disabled={isLoading || !inputQuery.trim()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity cursor-pointer shrink-0"
            aria-label="Dispatch analysis query"
          >
            <span>{isLoading ? "Running" : "Dispatch"}</span>
            {isLoading ? (
              <CornerDownLeft className="w-3.5 h-3.5" strokeWidth={1.6} />
            ) : (
              <ArrowUp className="w-3.5 h-3.5" strokeWidth={1.8} />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
