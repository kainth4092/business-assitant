"use client";

import React, { useState } from "react";
import { Copy, Check, PanelRightOpen, Database, FileText, Layers } from "lucide-react";
import { getRouteMeta } from "../lib/formatters";
import Stamp from "./Stamp";

export default function LogEntry({
  message,
  index,
  isSelected = false,
  highlightedCitationIndex = null,
  onSelectEvidence = () => {},
  onSelectCitation = () => {},
}) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  if (isUser) {
    return (
      <div className="pt-5 pb-3 border-b border-grid space-y-1.5">
        <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-muted">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded-xs border border-grid bg-sunken text-ink font-bold tabular-mono">
              Q_{String(index).padStart(2, "0")}
            </span>
            <span className="uppercase tracking-wider">Query Entry</span>
          </div>
          {message.timestamp && (
            <span className="tabular-mono">{message.timestamp}</span>
          )}
        </div>

        <h2 className="font-serif text-lg sm:text-xl font-semibold text-ink leading-snug break-words">
          {message.content}
        </h2>
      </div>
    );
  }

  const sources = message.sources || [];
  const trace = message.trace || {};
  const routeKey =
    trace.route ||
    (sources.some((s) => s.type === "sql") && sources.some((s) => s.type === "document")
      ? "both"
      : sources.some((s) => s.type === "sql")
      ? "data"
      : "docs");

  const routeMeta = getRouteMeta(routeKey);
  const RouteIcon =
    routeMeta.key === "data"
      ? Database
      : routeMeta.key === "both"
      ? Layers
      : FileText;

  const isGrounded = trace?.is_grounded ?? true;

  const renderInlineText = (text) => {
    const parts = text.split(/(\*\*.*?\*\*|`.*?`|\[\d+\])/g);
    return parts.map((part, pIdx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={pIdx} className="font-bold text-ink">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code
            key={pIdx}
            className="px-1 py-0.5 rounded-xs bg-sunken border border-grid font-mono text-[12.5px] text-ink break-words"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      const citMatch = /^\[(\d+)\]$/.exec(part);
      if (citMatch) {
        const citNum = Number.parseInt(citMatch[1], 10) - 1;
        const isHighlighted = isSelected && highlightedCitationIndex === citNum;
        return (
          <button
            key={pIdx}
            type="button"
            onClick={() => onSelectCitation(citNum)}
            onMouseEnter={() => onSelectCitation(citNum, { openDrawer: false })}
            className={`inline-flex items-center px-1 py-0 mx-0.5 rounded-xs border font-mono text-[11px] font-bold transition-colors cursor-pointer align-baseline ${
              isHighlighted
                ? "bg-highlighter text-highlighter-ink border-ink"
                : "bg-highlighter-wash text-ink border-grid-strong hover:bg-highlighter"
            }`}
            title={`Highlight source ${part} in evidence margin`}
          >
            {part}
          </button>
        );
      }
      return part;
    });
  };

  const renderFormattedContent = (content) => {
    if (!content) return null;
    const lines = content.split("\n");
    const elements = [];
    let tableRows = [];
    let inTable = false;

    const flushTable = (keySuffix) => {
      if (tableRows.length === 0) return;
      const header = tableRows[0];
      const body = tableRows.slice(1);
      elements.push(
        <div
          key={`table-${keySuffix}`}
          className="my-3 overflow-x-auto rounded-xs border border-grid bg-raised"
        >
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr className="border-b border-grid bg-sunken text-muted">
                {header.map((h, hIdx) => (
                  <th
                    key={hIdx}
                    className="px-2.5 py-1.5 uppercase tracking-wider text-[10.5px] font-bold"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-grid">
              {body.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => {
                    const looksNumeric = /^-?[\d,]+(\.\d+)?%?$/.test(cell.trim());
                    return (
                      <td
                        key={cIdx}
                        className={`px-2.5 py-1.5 text-ink tabular-mono ${
                          looksNumeric ? "text-right" : "text-left"
                        }`}
                      >
                        {cell}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
        inTable = true;
        if (!trimmed.includes("---")) {
          const cells = trimmed
            .split("|")
            .filter((_, i, a) => i > 0 && i < a.length - 1)
            .map((c) => c.trim());
          tableRows.push(cells);
        }
        return;
      }

      if (inTable) {
        inTable = false;
        flushTable(idx);
      }

      if (trimmed.startsWith("### ")) {
        elements.push(
          <h4
            key={idx}
            className="font-serif text-base font-semibold text-ink mt-3 mb-1"
          >
            {trimmed.slice(4)}
          </h4>
        );
        return;
      }

      if (trimmed.startsWith("## ")) {
        elements.push(
          <h3
            key={idx}
            className="font-serif text-lg font-semibold text-ink mt-4 mb-1.5 border-b border-grid pb-1"
          >
            {trimmed.slice(3)}
          </h3>
        );
        return;
      }

      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        elements.push(
          <li
            key={idx}
            className="ml-5 list-disc font-serif text-[15px] text-ink my-1 leading-relaxed"
          >
            {renderInlineText(trimmed.slice(2))}
          </li>
        );
        return;
      }

      if (/^\d+\.\s/.test(trimmed)) {
        elements.push(
          <div
            key={idx}
            className="ml-2 font-serif text-[15px] text-ink my-1 leading-relaxed"
          >
            {renderInlineText(trimmed)}
          </div>
        );
        return;
      }

      if (trimmed.length > 0) {
        elements.push(
          <p
            key={idx}
            className="font-serif text-[15.5px] text-ink my-2 leading-[1.7] break-words"
          >
            {renderInlineText(line)}
          </p>
        );
      }
    });

    if (inTable) {
      flushTable("end");
    }

    return elements;
  };

  return (
    <article
      className={`my-3 border rounded-xs bg-raised paper-stack transition-colors ${
        isSelected ? "border-ink" : "border-grid"
      }`}
      style={{
        borderInlineStartWidth: "3px",
        borderInlineStartColor: routeMeta.colorVar,
      }}
    >
      {/* Entry Header */}
      <div className="px-4 py-2.5 border-b border-grid bg-sunken/55 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs border font-mono text-[10.5px] font-bold uppercase tracking-wider"
            style={{
              color: routeMeta.inkVar,
              borderColor: routeMeta.colorVar,
              backgroundColor: routeMeta.tintVar,
            }}
          >
            <RouteIcon className="w-3 h-3" strokeWidth={1.6} />
            <span>{routeMeta.fullLabel}</span>
          </span>

          <Stamp
            variant={isGrounded ? "grounded" : "needs_review"}
            size="sm"
          />
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-xs border border-grid bg-raised text-muted hover:text-ink font-mono text-[10.5px] cursor-pointer"
            title="Copy answer text"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-sage-ink" strokeWidth={1.8} />
                <span className="text-sage-ink font-semibold">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" strokeWidth={1.6} />
                <span>Copy</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onSelectEvidence}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded-xs border font-mono text-[10.5px] font-bold cursor-pointer transition-colors ${
              isSelected
                ? "bg-highlighter text-highlighter-ink border-ink"
                : "bg-raised text-ink border-grid hover:border-grid-strong"
            }`}
          >
            <PanelRightOpen className="w-3 h-3" strokeWidth={1.6} />
            <span>Margin</span>
          </button>
        </div>
      </div>

      {/* Serif Log Body */}
      <div className="px-4 py-3.5">{renderFormattedContent(message.content)}</div>

      {/* Sources Footer */}
      <div className="px-4 py-2 border-t border-grid bg-sunken/40 flex flex-wrap items-center justify-between gap-2 font-mono text-[10.5px]">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted uppercase font-bold tracking-wider">
            Evidence:
          </span>
          {sources.length > 0 ? (
            sources.map((src, sIdx) => {
              const isDoc = src?.type === "document" || src?.file || src?.source_file;
              const label = isDoc
                ? (src.file || src.source_file || "Document").replace(/^docs\//, "")
                : "PostgreSQL SQL";
              const isHit = isSelected && highlightedCitationIndex === sIdx;
              return (
                <button
                  key={sIdx}
                  type="button"
                  onClick={() => onSelectCitation(sIdx)}
                  className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border cursor-pointer transition-colors ${
                    isHit
                      ? "bg-highlighter text-highlighter-ink border-ink font-bold"
                      : "bg-raised text-ink border-grid hover:border-grid-strong"
                  }`}
                >
                  <span>[{sIdx + 1}]</span>
                  <span className="truncate max-w-[160px]">{label}</span>
                </button>
              );
            })
          ) : (
            <span className="text-muted">Direct trace recorded</span>
          )}
        </div>

        <span className="text-muted tabular-mono">
          {trace?.retries ?? 0} {trace?.retries === 1 ? "retry" : "retries"}
        </span>
      </div>
    </article>
  );
}
