"use client";

import React, { useState } from "react";
import { Copy, Check, Layers, ChevronRight, Database, FileText, Sparkles, Share2 } from "lucide-react";
import CitationChip from "./CitationChip";

export default function ChatMessage({
  message,
  index,
  isSelected = false,
  onSelectEvidence = () => {},
  isStreaming = false
}) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ----------------------------------------------------------------------------
  // User Question Entry
  // ----------------------------------------------------------------------------
  if (isUser) {
    return (
      <div className="py-5 border-b border-border group animate-fade-up space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container border border-border text-primary font-bold">
              #QRY-{String(index).padStart(2, "0")}
            </span>
            <span className="font-mono text-[11px] text-muted font-medium">
              {message.timestamp || ""}
            </span>
          </div>
          <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-accent-lime/10 text-primary border border-accent-lime/30 font-semibold">
            USER PROMPT
          </span>
        </div>

        <h3 className="font-headline font-bold text-[20px] md:text-[22px] text-primary tracking-tight leading-snug">
          {message.content}
        </h3>
      </div>
    );
  }

  // ----------------------------------------------------------------------------
  // Assistant Answer Entry (Card with Left Chartreuse / Lime Accent Border)
  // ----------------------------------------------------------------------------
  const sources = message.sources || [];
  const trace = message.trace || {};
  const route = trace.route || (sources.some(s => s.type === "sql") && sources.some(s => s.type === "document") ? "both" : sources.some(s => s.type === "sql") ? "data" : "docs");

  const routeStyles = {
    data: {
      border: "border-l-accent-cyan",
      badge: "bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30",
      label: "DATA (SQL)",
      icon: Database,
    },
    docs: {
      border: "border-l-accent-amber",
      badge: "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
      label: "DOCS (RAG)",
      icon: FileText,
    },
    both: {
      border: "border-l-accent-lime",
      badge: "bg-accent-lime/15 text-primary border-accent-lime/40",
      label: "MULTI-SOURCE",
      icon: Layers,
    },
  }[route] || {
    border: "border-l-accent-lime",
    badge: "bg-surface-container text-muted border-border",
    label: "ANALYSIS",
    icon: Sparkles,
  };

  const RouteIcon = routeStyles.icon;

  // Inline formatting: bold, code, and source citations like [1]
  const renderInlineMarkdown = (text) => {
    const parts = text.split(/(\*\*.*?\*\*|`.*?`|\[\d+\])/g);
    return parts.map((part, pIdx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={pIdx} className="font-bold text-primary">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={pIdx} className="px-1.5 py-0.5 rounded bg-surface-container font-mono text-[12.5px] text-primary border border-border">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (/^\[\d+\]$/.test(part)) {
        return (
          <button
            key={pIdx}
            type="button"
            onClick={onSelectEvidence}
            className="inline-flex items-center px-1.5 py-0.2 mx-0.5 rounded font-mono text-[11px] font-bold bg-accent-lime/15 text-primary hover:bg-accent-lime hover:text-accent-lime-contrast border border-accent-lime/30 transition-colors"
            title="Inspect source in Evidence panel"
          >
            {part}
          </button>
        );
      }
      return part;
    });
  };

  // Content lines parser
  const renderFormattedContent = (content) => {
    if (!content) return null;
    const lines = content.split("\n");
    const elements = [];
    let tableRows = [];
    let inTable = false;

    lines.forEach((line, idx) => {
      // Check for markdown table line
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        inTable = true;
        if (!line.includes("---")) {
          const cells = line.split("|").filter((c, i, a) => i > 0 && i < a.length - 1).map((c) => c.trim());
          tableRows.push(cells);
        }
        return;
      }

      if (inTable && (!line.trim().startsWith("|") || idx === lines.length - 1)) {
        inTable = false;
        if (tableRows.length > 0) {
          const header = tableRows[0];
          const body = tableRows.slice(1);
          elements.push(
            <div key={`table-${idx}`} className="my-3 overflow-x-auto rounded-lg border border-border bg-surface-low">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-border bg-surface-container text-primary font-bold">
                    {header.map((h, hIdx) => (
                      <th key={hIdx} className="px-3 py-2 uppercase tracking-wider text-[10.5px]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {body.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-surface transition-colors">
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 text-primary tabular-nums">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          tableRows = [];
        }
      }

      // Headers
      if (line.startsWith("### ")) {
        elements.push(
          <h4 key={idx} className="font-headline text-headline-md font-bold text-primary mt-3 mb-1">
            {line.replace("### ", "")}
          </h4>
        );
        return;
      }
      if (line.startsWith("## ")) {
        elements.push(
          <h3 key={idx} className="font-headline text-headline-lg font-bold text-primary mt-4 mb-2 border-b border-border pb-1">
            {line.replace("## ", "")}
          </h3>
        );
        return;
      }

      // Bullet points
      if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        const itemText = line.trim().substring(2);
        elements.push(
          <li key={idx} className="ml-4 list-disc text-body-base text-primary my-1 leading-relaxed">
            {renderInlineMarkdown(itemText)}
          </li>
        );
        return;
      }

      // Numbered lists
      if (/^\d+\.\s/.test(line.trim())) {
        elements.push(
          <div key={idx} className="ml-2 text-body-base text-primary my-1 leading-relaxed">
            {renderInlineMarkdown(line.trim())}
          </div>
        );
        return;
      }

      // Normal paragraph
      if (line.trim().length > 0) {
        elements.push(
          <p key={idx} className="text-body-base text-primary my-1.5 leading-relaxed">
            {renderInlineMarkdown(line)}
          </p>
        );
      }
    });

    // Flush any pending table at the end
    if (inTable && tableRows.length > 0) {
      const header = tableRows[0];
      const body = tableRows.slice(1);
      elements.push(
        <div key="table-end" className="my-3 overflow-x-auto rounded-lg border border-border bg-surface-low">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-border bg-surface-container text-primary font-bold">
                {header.map((h, hIdx) => (
                  <th key={hIdx} className="px-3 py-2 uppercase tracking-wider text-[10.5px]">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {body.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-surface transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3 py-2 text-primary tabular-nums">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return elements;
  };

  return (
    <article
      className={`p-5 rounded-lg bg-surface border border-border border-l-4 ${routeStyles.border} shadow-card my-4 transition-all animate-fade-up`}
    >
      {/* Top Header inside Assistant Card */}
      <div className="flex items-center justify-between pb-3.5 mb-3 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-accent-lime/20 flex items-center justify-center text-primary">
            <Sparkles className="w-3.5 h-3.5 stroke-[2.2]" />
          </div>
          <span className="font-headline text-headline-md font-bold text-primary">
            Synthesized Intelligence
          </span>
          <span className="px-2 py-0.5 rounded bg-surface-container border border-border font-mono text-label-telemetry text-muted font-medium hidden sm:inline">
            Agent Engine v3.8
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Route badge */}
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono text-label-telemetry border font-semibold ${routeStyles.badge}`}>
            <RouteIcon className="w-3 h-3 stroke-[2.2]" />
            <span>{routeStyles.label}</span>
          </span>

          {/* Copy Button */}
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono text-muted hover:text-primary hover:bg-surface-high border border-border transition-colors"
            title="Copy answer text"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-accent-emerald stroke-[2.2]" />
                <span className="text-[10px] text-accent-emerald font-bold">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 stroke-[1.8]" />
                <span className="text-[10px] font-medium">Copy</span>
              </>
            )}
          </button>

          {/* Inspect Evidence Button */}
          <button
            type="button"
            onClick={onSelectEvidence}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono font-bold transition-all ${
              isSelected
                ? "bg-accent-lime text-accent-lime-contrast shadow-xs"
                : "bg-surface-container text-primary hover:bg-accent-lime hover:text-accent-lime-contrast border border-border"
            }`}
          >
            <Layers className="w-3 h-3 stroke-[2]" />
            <span className="text-[10px]">Evidence</span>
            <ChevronRight className="w-3 h-3 stroke-[2]" />
          </button>
        </div>
      </div>

      {/* Prose Body */}
      <div className="font-body text-body-base text-primary leading-relaxed space-y-1">
        {renderFormattedContent(message.content)}
        {isStreaming && <span className="streaming-cursor" />}
      </div>

      {/* Citations Footer */}
      <div className="mt-4 pt-3 border-t border-border flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-label-telemetry text-muted uppercase font-bold mr-1">
            Sources Cited:
          </span>
          {sources.length > 0 ? (
            sources.map((src, sIdx) => (
              <CitationChip
                key={sIdx}
                index={sIdx}
                source={src}
                isSelected={isSelected}
                onClick={onSelectEvidence}
              />
            ))
          ) : (
            <span className="text-[11.5px] font-mono text-muted italic">
              PostgreSQL Relational Sales &middot; Direct Analysis
            </span>
          )}
        </div>

        <div className="font-mono text-[10.5px] text-muted">
          Grounded validation &middot; {trace?.retries ?? 0} retries
        </div>
      </div>
    </article>
  );
}
