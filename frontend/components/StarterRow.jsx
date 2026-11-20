"use client";

import React from "react";
import { ArrowRight, Database, FileText, Layers } from "lucide-react";

export default function StarterRow({
  num,
  query,
  caption,
  route = "data",
  onSelect = () => {},
  index = 0
}) {
  const routeConfigs = {
    data: {
      label: "DATA (SQL)",
      icon: Database,
      badge: "bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30",
      borderLeft: "border-l-accent-cyan",
    },
    docs: {
      label: "DOCS (RAG)",
      icon: FileText,
      badge: "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
      borderLeft: "border-l-accent-amber",
    },
    both: {
      label: "MULTI-SOURCE",
      icon: Layers,
      badge: "bg-accent-lime/15 text-primary border-accent-lime/40",
      borderLeft: "border-l-accent-lime",
    },
  }[route] || {
    label: route.toUpperCase(),
    icon: Database,
    badge: "bg-surface-container text-muted border-border",
    borderLeft: "border-l-border",
  };

  const Icon = routeConfigs.icon;

  return (
    <button
      type="button"
      onClick={() => onSelect(query, route)}
      style={{ animationDelay: `${index * 60}ms` }}
      className={`w-full text-left p-2.5 sm:p-3 bg-surface hover:bg-surface-low rounded-lg border border-border border-l-4 ${routeConfigs.borderLeft} shadow-xs hover:shadow-card-hover hover:-translate-y-0.5 active:scale-[0.99] transition-all duration-fast flex items-center justify-between gap-3 group`}
    >
      <div className="flex items-start gap-2.5 min-w-0">
        <span className="font-mono text-xs font-bold text-muted tabular-nums pt-0.5 group-hover:text-primary transition-colors">
          {num}
        </span>
        <div className="min-w-0 space-y-0.5">
          <div className="font-headline text-[13px] sm:text-[14px] text-primary font-bold group-hover:text-accent-cyan transition-colors leading-snug">
            {query}
          </div>
          {caption && (
            <p className="font-body text-[11px] sm:text-xs text-muted line-clamp-1 leading-normal">
              {caption}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2.5 shrink-0 pl-2">
        <span
          className={`font-mono text-label-telemetry px-2 py-0.5 rounded border flex items-center gap-1 font-semibold ${routeConfigs.badge}`}
        >
          <Icon className="w-3 h-3 stroke-[2.2]" />
          <span>{routeConfigs.label}</span>
        </span>
        <div className="w-7 h-7 rounded flex items-center justify-center text-muted group-hover:text-primary group-hover:bg-surface-container transition-all">
          <ArrowRight className="w-4 h-4 stroke-[2.2] group-hover:translate-x-0.5 transition-transform" />
        </div>
      </div>
    </button>
  );
}
