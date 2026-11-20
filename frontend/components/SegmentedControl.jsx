"use client";

import React from "react";
import { motion } from "framer-motion";
import { Compass, Database, FileText, Layers } from "lucide-react";

const OPTIONS = [
  { id: "auto", label: "Auto", icon: Compass, color: "text-accent-lime" },
  { id: "data", label: "Data", icon: Database, color: "text-accent-cyan" },
  { id: "docs", label: "Docs", icon: FileText, color: "text-accent-amber" },
  { id: "both", label: "Both", icon: Layers, color: "text-accent-lime" },
];

export default function SegmentedControl({
  selectedRoute = "auto",
  onChange = () => {}
}) {
  return (
    <div className="inline-flex items-center p-0.5 rounded-md bg-surface-container border border-border gap-0.5 relative select-none">
      {OPTIONS.map((opt) => {
        const Icon = opt.icon;
        const isCurrent = selectedRoute === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onChange(opt.id)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold transition-colors relative z-10 ${
              isCurrent ? "text-primary" : "text-muted hover:text-primary"
            }`}
          >
            {isCurrent && (
              <motion.div
                layoutId="activeSegmentedPill"
                className="absolute inset-0 bg-surface rounded border border-border shadow-xs z-[-1]"
                transition={{ type: "spring", stiffness: 450, damping: 32 }}
              />
            )}
            <Icon
              className={`w-3.5 h-3.5 stroke-[2.2] ${
                isCurrent ? opt.color : "text-muted"
              }`}
            />
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
