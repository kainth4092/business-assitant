"use client";

import React, { useState, useEffect } from "react";

export function useCountUp(targetNumber, duration = 600) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!targetNumber || targetNumber <= 0) return;
    let startTimestamp = null;
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const easedProgress = 1 - (1 - progress) * (1 - progress);
      setCount(Math.floor(easedProgress * targetNumber));
      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        setCount(targetNumber);
      }
    };
    window.requestAnimationFrame(step);
  }, [targetNumber, duration]);

  return count;
}

export default function StatTile({
  icon: Icon,
  value,
  label,
  accent = "cyan",
  badge = null
}) {
  const isNumeric = typeof value === "number" || (!isNaN(parseInt(value, 10)) && !isNaN(Number(String(value).replace(/,/g, ""))));
  const numericValue = isNumeric ? (typeof value === "number" ? value : parseInt(String(value).replace(/,/g, ""), 10)) : 0;
  const animatedCount = useCountUp(numericValue, 600);
  const displayValue = isNumeric && numericValue > 0 ? animatedCount.toLocaleString() : value;

  const colorStyles = {
    cyan: {
      border: "border-l-accent-cyan",
      badge: "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
      iconColor: "text-accent-cyan",
      valueColor: "text-primary",
    },
    amber: {
      border: "border-l-accent-amber",
      badge: "bg-accent-amber/15 text-accent-amber border-accent-amber/30",
      iconColor: "text-accent-amber",
      valueColor: "text-primary",
    },
    lime: {
      border: "border-l-accent-lime",
      badge: "bg-accent-lime/20 text-primary border-accent-lime/40",
      iconColor: "text-accent-lime",
      valueColor: "text-primary",
    },
    emerald: {
      border: "border-l-accent-emerald",
      badge: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30",
      iconColor: "text-accent-emerald",
      valueColor: "text-accent-emerald",
    },
  }[accent] || {
    border: "border-l-border",
    badge: "bg-surface-container text-muted border-border",
    iconColor: "text-muted",
    valueColor: "text-primary",
  };

  return (
    <div className={`p-3 sm:p-3.5 rounded-xl bg-surface-low border border-border border-l-4 ${colorStyles.border} shadow-xs flex flex-col justify-between gap-2.5 transition-all hover:bg-surface hover:shadow-card-hover`}>
      {/* Top row: Label + optional Badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {Icon && <Icon className={`w-4 h-4 shrink-0 ${colorStyles.iconColor} stroke-[2]`} />}
          <span className="font-mono text-[11px] uppercase text-muted font-bold tracking-wider truncate" title={label}>
            {label}
          </span>
        </div>
        {badge && (
          <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded border shrink-0 font-bold ${colorStyles.badge}`}>
            {badge}
          </span>
        )}
      </div>

      {/* Bottom row: Clean large metric value */}
      <div className={`font-mono text-[22px] sm:text-[25px] font-bold tracking-tight tabular-nums leading-none ${colorStyles.valueColor}`}>
        {displayValue}
      </div>
    </div>
  );
}
