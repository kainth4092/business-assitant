"use client";

import React from "react";
import { ArrowDownRight, CheckCircle2 } from "lucide-react";

export default function QualityBars({
  title,
  labelBefore = "Raw Input",
  valBefore = 0,
  labelAfter = "Cleaned",
  valAfter = 0,
  maxVal,
  unit = "",
  deltaLabel = null
}) {
  const max = maxVal || Math.max(valBefore, valAfter, 1);
  const pctBefore = Math.min(100, Math.max(valBefore > 0 ? 6 : 0, (valBefore / max) * 100));
  const pctAfter = Math.min(100, Math.max(valAfter > 0 ? 6 : 0, (valAfter / max) * 100));
  
  const diff = valBefore - valAfter;
  const percentResolved = valBefore > 0 ? Math.round((diff / valBefore) * 100) : 100;

  return (
    <div className="p-3.5 rounded-lg bg-surface border border-border space-y-2 text-xs">
      <div className="flex items-center justify-between">
        <span className="font-mono text-code-md text-primary font-semibold flex items-center gap-1.5">
          {title}
        </span>
        <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container text-accent-lime font-bold flex items-center gap-1">
          <ArrowDownRight className="w-3 h-3 stroke-[2.5]" />
          {deltaLabel || `${percentResolved}% resolved`}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 items-center pt-1">
        {/* Before bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] font-mono text-muted">
            <span>{labelBefore}</span>
            <span className="font-bold text-accent-crimson tabular-nums">
              {valBefore.toLocaleString()}{unit}
            </span>
          </div>
          <div className="w-full bg-surface-container-highest rounded-full h-2 overflow-hidden border border-border">
            <div
              className="bg-accent-crimson/80 h-full rounded-full transition-all duration-normal"
              style={{ width: `${pctBefore}%` }}
            />
          </div>
        </div>

        {/* After bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] font-mono text-muted">
            <span>{labelAfter}</span>
            <span className="font-bold text-accent-emerald tabular-nums">
              {valAfter.toLocaleString()}{unit}
            </span>
          </div>
          <div className="w-full bg-surface-container-highest rounded-full h-2 overflow-hidden border border-border">
            <div
              className="bg-accent-emerald h-full rounded-full transition-all duration-normal"
              style={{ width: `${pctAfter}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
