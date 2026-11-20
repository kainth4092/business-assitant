"use client";

import React from "react";
import { FileText, Database } from "lucide-react";

export default function CitationChip({
  index,
  source,
  onClick = () => {},
  isSelected = false
}) {
  const isDoc = source?.type === "document" || source?.file;
  const isSql = source?.type === "sql" || source?.query;

  const fileName = source?.file || source?.source_file;
  const label = isDoc
    ? (fileName ? fileName.replace(/^docs\//, "") : "Policy Doc")
    : isSql
    ? "PostgreSQL"
    : "Source";

  const colorClass = isDoc
    ? "bg-accent-amber/10 text-accent-amber border-accent-amber/30 hover:border-accent-amber"
    : isSql
    ? "bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30 hover:border-accent-cyan"
    : "bg-surface-container text-muted border-border hover:text-primary";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono text-[11px] border transition-all ${colorClass} ${
        isSelected ? "ring-1 ring-current font-bold shadow-xs" : "font-medium"
      }`}
      title={isDoc ? `Vector source: ${fileName || "document"}` : "SQL sales query"}
    >
      {isDoc && <FileText className="w-3 h-3 stroke-[2]" />}
      {isSql && <Database className="w-3 h-3 stroke-[2]" />}
      <span>
        [{index !== undefined ? index + 1 : ""}] {label}
      </span>
    </button>
  );
}
