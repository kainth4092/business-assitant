"use client";

import React from "react";
import { motion } from "motion/react";
import { Compass, Database, FileText, Layers } from "lucide-react";

const ROUTES = [
  { id: "auto", label: "Auto", icon: Compass, swatchVar: "var(--ink)" },
  { id: "data", label: "Data", icon: Database, swatchVar: "var(--route-data)" },
  { id: "docs", label: "Docs", icon: FileText, swatchVar: "var(--route-docs)" },
  { id: "both", label: "Both", icon: Layers, swatchVar: "var(--route-both)" },
];

export default function SegmentedControl({
  selectedRoute = "auto",
  onChange = () => {},
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Query routing mode"
      className="inline-flex items-center border border-grid bg-sunken rounded-xs p-0.5 gap-0.5 select-none"
    >
      {ROUTES.map((opt) => {
        const Icon = opt.icon;
        const active = selectedRoute === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.id)}
            className={`relative z-10 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs font-mono text-[11px] font-semibold uppercase tracking-wider transition-colors cursor-pointer ${
              active ? "text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {active && (
              <motion.span
                layoutId="stationeryRouteTab"
                transition={{ type: "spring", stiffness: 500, damping: 36 }}
                className="absolute inset-0 bg-raised border border-grid-strong rounded-xs -z-10"
                style={{
                  borderBottomWidth: "2px",
                  borderBottomColor: opt.swatchVar,
                }}
              />
            )}
            <Icon
              className="w-3 h-3 shrink-0"
              strokeWidth={1.6}
              style={{ color: active ? opt.swatchVar : "currentColor" }}
            />
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
