"use client";

import React from "react";
import { FileText, ChevronRight } from "lucide-react";

export default function IndexCard({
  doc,
  isSelected = false,
  onSelect = () => {},
  onAskQuestion = () => {},
}) {
  const fileName = doc.source_file || "untitled";
  const docTitle =
    doc.sample_title ||
    fileName.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
  const fileExt = fileName.includes(".")
    ? fileName.split(".").pop().toUpperCase()
    : "DOC";
  const chunkCount = Number(doc.total_chunks || 0);
  const openingLines =
    doc.sample_summary || "Indexed in pgvector for semantic retrieval.";

  return (
    <article
      className={`border rounded-xs transition-[transform,border-color,background-color] duration-150 hover:-translate-y-px flex flex-col justify-between ${
        isSelected
          ? "border-ink bg-highlighter-wash paper-stack-strong"
          : "border-grid bg-raised hover:border-grid-strong paper-stack"
      }`}
      style={{
        borderTopWidth: "3px",
        borderTopColor: "var(--route-docs)",
      }}
    >
      <button
        type="button"
        onClick={() => onSelect(doc)}
        className="w-full text-left p-3.5 space-y-2.5 cursor-pointer flex-1"
      >
        <div className="flex items-center justify-between gap-2 font-mono text-[10.5px]">
          <span className="px-1.5 py-0.5 rounded-xs border border-grid bg-sunken text-ink font-bold uppercase shrink-0">
            .{fileExt}
          </span>
          <span className="text-route-docs-ink font-bold tabular-mono shrink-0">
            {chunkCount.toLocaleString()} {chunkCount === 1 ? "chunk" : "chunks"}
          </span>
        </div>

        <h3 className="font-serif text-base font-semibold text-ink leading-snug line-clamp-2 break-words">
          {docTitle}
        </h3>

        <div
          className={`flex items-center gap-1.5 font-mono text-[11px] min-w-0 ${
            isSelected ? "text-ink" : "text-muted"
          }`}
        >
          <FileText className="w-3.5 h-3.5 text-route-docs-ink shrink-0" strokeWidth={1.5} />
          <span className="truncate" title={fileName}>
            {fileName}
          </span>
        </div>

        <p
          className={`font-sans text-xs leading-relaxed line-clamp-3 break-words ${
            isSelected ? "text-ink" : "text-muted"
          }`}
        >
          {openingLines}
        </p>
      </button>

      <div className="px-3.5 py-2 border-t border-grid bg-sunken/50 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onSelect(doc)}
          className="font-mono text-[11px] font-semibold text-ink hover:underline cursor-pointer"
        >
          {isSelected ? "Inspecting chunks" : "Inspect chunks"}
        </button>

        <button
          type="button"
          onClick={() =>
            onAskQuestion(
              `Summarize the operational rules and key points from ${fileName}`
            )
          }
          className="inline-flex items-center gap-1 px-2 py-1 rounded-xs border border-grid bg-raised hover:border-ink font-mono text-[10.5px] font-bold text-ink cursor-pointer"
        >
          <span>Ask</span>
          <ChevronRight className="w-3 h-3" strokeWidth={1.8} />
        </button>
      </div>
    </article>
  );
}
