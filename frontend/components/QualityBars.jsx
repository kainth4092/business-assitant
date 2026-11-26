"use client";

import React from "react";
import { ArrowDownRight } from "lucide-react";

export default function QualityBars({
  title,
  labelBefore = "Before",
  valBefore = 0,
  labelAfter = "After",
  valAfter = 0,
  maxVal,
  unit = "",
  deltaLabel = null,
}) {
  const max = maxVal || Math.max(valBefore, valAfter, 1);
  const pctBefore = Math.min(100, Math.max(valBefore > 0 ? 4 : 0, (valBefore / max) * 100));
  const pctAfter = Math.min(100, Math.max(valAfter > 0 ? 4 : 0, (valAfter / max) * 100));

  const diff = valBefore - valAfter;
  const percentResolved = valBefore > 0 ? Math.round((diff / valBefore) * 100) : 100;

  return (
    <div className="p-3 rounded-xs bg-raised border border-grid space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-ink font-semibold truncate">
          {title}
        </span>
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs bg-sage-tint border border-sage/40 font-mono text-[10px] font-bold text-sage-ink shrink-0">
          <ArrowDownRight className="w-3 h-3" strokeWidth={1.6} />
          {deltaLabel || `${percentResolved}% resolved`}
        </span>
      </div>

      <div className="space-y-2">
        {/* Before ruled bar */}
        <div className="space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
              {labelBefore}
            </span>
            <span className="font-mono text-base font-bold text-seal-ink tabular-mono leading-none">
              {Number(valBefore).toLocaleString()}
              {unit}
            </span>
          </div>
          <div className="w-full h-2.5 bg-sunken border border-grid rounded-xs overflow-hidden relative">
            <div
              className="h-full transition-[width] duration-300"
              style={{ width: `${pctBefore}%`, backgroundColor: "var(--seal-red)" }}
            />
          </div>
        </div>

        {/* After ruled bar */}
        <div className="space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
              {labelAfter}
            </span>
            <span className="font-mono text-base font-bold text-sage-ink tabular-mono leading-none">
              {Number(valAfter).toLocaleString()}
              {unit}
            </span>
          </div>
          <div className="w-full h-2.5 bg-sunken border border-grid rounded-xs overflow-hidden relative">
            <div
              className="h-full transition-[width] duration-300"
              style={{ width: `${pctAfter}%`, backgroundColor: "var(--sage)" }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
