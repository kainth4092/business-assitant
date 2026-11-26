"use client";

import React from "react";
import { X, BookOpen, Database, FileText } from "lucide-react";
import Timeline from "./Timeline";
import SqlBlock from "./SqlBlock";
import DataTable from "./DataTable";
import Stamp from "./Stamp";

export default function Margin({
  activeEvidence,
  highlightedCitationIndex = null,
  onClose,
  isLoading = false,
  activeLiveStep = null,
  liveMessage = null,
}) {
  if (!activeEvidence && !isLoading) {
    return (
      <aside
        className="w-full h-full flex flex-col justify-between p-4 bg-raised text-ink border-s border-grid"
        aria-label="Evidence margin notes"
      >
        <div className="flex items-center justify-between pb-2.5 border-b border-grid">
          <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider">
            <span className="w-2 h-2 rounded-xs bg-grid-strong" />
            <span>Margin Notes</span>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-xs border border-transparent hover:border-grid text-muted hover:text-ink cursor-pointer"
              aria-label="Close evidence margin"
            >
              <X className="w-4 h-4" strokeWidth={1.6} />
            </button>
          )}
        </div>

        <div className="my-auto py-8 px-2 text-center space-y-2">
          <div className="font-serif text-base font-semibold text-ink">
            Evidence Margin Empty
          </div>
          <p className="text-xs text-muted leading-relaxed max-w-xs mx-auto">
            Run a question or click any citation marker <code className="font-mono">[1]</code> in the log to inspect the step timeline, SQL query, result table, and document chunks.
          </p>
        </div>

        <div className="p-3 rounded-xs border border-grid bg-sunken/70 font-mono text-[10.5px] text-muted space-y-1.5">
          <div className="font-bold text-ink uppercase tracking-wider">
            Pipeline Architecture
          </div>
          <div>01 Route → 02 Query / Retrieve → 03 Answer → 04 Check</div>
        </div>
      </aside>
    );
  }

  const {
    tools_used = [],
    sources = [],
    trace = {},
    messageIndex,
  } = activeEvidence || {};

  const sqlSource = sources.find((s) => s.type === "sql" || s.query);
  const docSources = sources
    .map((s, originalIdx) => ({ ...s, _originalIdx: originalIdx }))
    .filter((s) => s.type === "document" || s.file || s.source_file);

  const retries = trace.retries ?? 0;
  const isGrounded = trace.is_grounded ?? true;

  return (
    <aside
      id="evidence-panel"
      aria-label="Evidence margin notes"
      className="w-full h-full bg-raised flex flex-col overflow-y-auto"
    >
      {/* Margin Header */}
      <div className="sticky top-0 z-10 px-4 py-3 border-b border-grid bg-raised flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`w-2 h-2 rounded-xs shrink-0 ${
              isLoading ? "bg-highlighter border border-ink" : "bg-sage"
            }`}
          />
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-ink truncate">
            Margin Notes
          </span>
          {messageIndex && (
            <span className="px-1.5 py-0.5 rounded-xs border border-grid bg-sunken font-mono text-[10px] font-bold text-ink tabular-mono">
              Q_{String(messageIndex).padStart(2, "0")}
            </span>
          )}
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-xs border border-transparent hover:border-grid text-muted hover:text-ink cursor-pointer shrink-0"
            aria-label="Close evidence margin"
          >
            <X className="w-4 h-4" strokeWidth={1.6} />
          </button>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Live status region when running */}
        {isLoading && (
          <div
            role="status"
            aria-live="polite"
            className="p-2.5 rounded-xs border border-ink bg-highlighter-wash font-mono text-xs text-ink font-semibold"
          >
            {liveMessage || "Executing LangGraph agent pipeline..."}
          </div>
        )}

        {/* 1. Vertical Timeline of Agent Steps */}
        <section className="space-y-2">
          <div className="flex items-center justify-between font-mono text-[10.5px] uppercase tracking-wider text-muted font-bold">
            <span>Execution Steps</span>
            <span className="tabular-mono">
              {tools_used.length} {tools_used.length === 1 ? "tool" : "tools"} · {retries} retries
            </span>
          </div>
          <Timeline
            mode="vertical"
            trace={trace}
            toolsUsed={tools_used}
            isLoading={isLoading}
            activeLiveStep={activeLiveStep}
            liveMessage={liveMessage}
          />
        </section>

        {/* 2. SQL Query & Tabular Results */}
        {sqlSource && (
          <section className="space-y-2" id="evidence-sql">
            <div className="flex items-center justify-between font-mono text-[10.5px] uppercase tracking-wider text-muted font-bold">
              <span className="inline-flex items-center gap-1.5 text-route-data-ink">
                <Database className="w-3.5 h-3.5" strokeWidth={1.5} />
                SQL Evidence
              </span>
              <span>Read-only</span>
            </div>

            <SqlBlock
              sql={sqlSource.query || "-- SQL statement recorded"}
              executionTime={
                trace.latency || trace.execution_time_ms
                  ? `${trace.latency || trace.execution_time_ms}ms`
                  : null
              }
            />

            {Array.isArray(sqlSource.results) && sqlSource.results.length > 0 && (
              <DataTable
                rows={sqlSource.results}
                maxRows={6}
                title="Query Result"
              />
            )}
          </section>
        )}

        {/* 3. Retrieved Document Tags & Relevance Bars */}
        {docSources.length > 0 && (
          <section className="space-y-2" id="evidence-rag">
            <div className="flex items-center justify-between font-mono text-[10.5px] uppercase tracking-wider text-muted font-bold">
              <span className="inline-flex items-center gap-1.5 text-route-docs-ink">
                <BookOpen className="w-3.5 h-3.5" strokeWidth={1.5} />
                Document Tags
              </span>
              <span className="tabular-mono">{docSources.length} retrieved</span>
            </div>

            <div className="space-y-2">
              {docSources.map((doc, idx) => {
                const citationIdx = doc._originalIdx;
                const isHighlighted = highlightedCitationIndex === citationIdx;
                const fileName =
                  doc.file || doc.source_file || doc.title || `Source #${idx + 1}`;
                const score =
                  typeof doc.similarity === "number"
                    ? doc.similarity
                    : typeof doc.score === "number"
                    ? doc.score
                    : null;
                const pct =
                  score !== null
                    ? Math.min(100, Math.max(0, Math.round(score > 1 ? score : score * 100)))
                    : null;

                return (
                  <div
                    key={idx}
                    className={`p-3 rounded-xs border transition-colors space-y-2 ${
                      isHighlighted
                        ? "border-ink bg-highlighter-wash"
                        : "border-grid bg-paper/60"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0 font-mono text-xs">
                        <span className="px-1 py-0.2 rounded-xs border border-grid bg-raised font-bold text-ink shrink-0">
                          [{citationIdx + 1}]
                        </span>
                        <FileText className="w-3.5 h-3.5 text-route-docs-ink shrink-0" strokeWidth={1.5} />
                        <span className="font-semibold text-ink truncate" title={fileName}>
                          {fileName}
                        </span>
                      </div>
                      {pct !== null && (
                        <span className="font-mono text-[10.5px] font-bold text-route-docs-ink tabular-mono shrink-0">
                          {pct}%
                        </span>
                      )}
                    </div>

                    {(doc.content || doc.text || doc.snippet) && (
                      <p className="font-sans text-xs text-ink/90 leading-relaxed line-clamp-3 break-words">
                        {doc.content || doc.text || doc.snippet}
                      </p>
                    )}

                    {/* Relevance Bar */}
                    {pct !== null && (
                      <div className="w-full h-1.5 bg-sunken border border-grid rounded-xs overflow-hidden">
                        <div
                          className="h-full"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: "var(--route-docs)",
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* 4. Groundedness Stamp */}
        {activeEvidence && (
          <section className="p-3 rounded-xs border border-grid bg-sunken/60 flex items-center justify-between gap-2">
            <div className="font-mono text-xs text-ink font-semibold">
              Groundedness Audit
            </div>
            <Stamp
              variant={isGrounded ? "grounded" : "needs_review"}
              shape="square"
              size="sm"
            />
          </section>
        )}
      </div>
    </aside>
  );
}
