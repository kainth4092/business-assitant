"use client";

import React from "react";

/**
 * Hanko-inspired operational seal stamp.
 * Variants:
 * - "approved" | "applied" | "pass" | "grounded" -> sage or seal red (approvals use seal red)
 * - "rejected" | "flagged" | "error" -> seal red
 * - "review" | "needs_review" | "warn" -> amber
 * - "triage" | "new" -> ink blue / muted
 */
const STAMP_MAP = {
  approved: {
    label: "APPROVED",
    colorVar: "var(--seal-red-ink)",
    borderVar: "var(--seal-red)",
    bgVar: "var(--seal-red-tint)",
  },
  applied: {
    label: "APPLIED",
    colorVar: "var(--sage-ink)",
    borderVar: "var(--sage)",
    bgVar: "var(--sage-tint)",
  },
  rejected: {
    label: "REJECTED",
    colorVar: "var(--seal-red-ink)",
    borderVar: "var(--seal-red)",
    bgVar: "var(--seal-red-tint)",
  },
  flagged: {
    label: "FLAGGED",
    colorVar: "var(--seal-red-ink)",
    borderVar: "var(--seal-red)",
    bgVar: "var(--seal-red-tint)",
  },
  needs_review: {
    label: "NEEDS REVIEW",
    colorVar: "var(--seal-red-ink)",
    borderVar: "var(--seal-red)",
    bgVar: "var(--seal-red-tint)",
  },
  fix_ready: {
    label: "NEEDS REVIEW",
    colorVar: "var(--seal-red-ink)",
    borderVar: "var(--seal-red)",
    bgVar: "var(--seal-red-tint)",
  },
  investigating: {
    label: "INVESTIGATING",
    colorVar: "var(--route-data-ink)",
    borderVar: "var(--route-data)",
    bgVar: "var(--route-data-tint)",
  },
  new: {
    label: "NEW",
    colorVar: "var(--ink)",
    borderVar: "var(--grid-strong)",
    bgVar: "var(--bg-sunken)",
  },
  pass: {
    label: "PASS",
    colorVar: "var(--sage-ink)",
    borderVar: "var(--sage)",
    bgVar: "var(--sage-tint)",
  },
  warn: {
    label: "RESOLVED",
    colorVar: "var(--amber-ink)",
    borderVar: "var(--amber)",
    bgVar: "var(--amber-tint)",
  },
  grounded: {
    label: "GROUNDED",
    colorVar: "var(--sage-ink)",
    borderVar: "var(--sage)",
    bgVar: "var(--sage-tint)",
  },
};

export default function Stamp({
  variant = "needs_review",
  label = null,
  shape = "square", // "square" | "circle"
  animate = false,
  size = "sm", // "sm" | "md"
  className = "",
}) {
  const cfg = STAMP_MAP[variant] || STAMP_MAP.new;
  const text = label || cfg.label;

  if (shape === "circle") {
    return (
      <span
        className={`inline-flex items-center justify-center shrink-0 select-none ${
          animate ? "animate-stamp-drop" : "-rotate-2"
        } ${className}`}
        style={{ color: cfg.colorVar }}
      >
        <svg
          width={size === "md" ? 64 : 50}
          height={size === "md" ? 64 : 50}
          viewBox="0 0 64 64"
          aria-label={text}
          role="img"
        >
          <circle
            cx="32"
            cy="32"
            r="28"
            fill={cfg.bgVar}
            stroke={cfg.borderVar}
            strokeWidth="2"
          />
          <circle
            cx="32"
            cy="32"
            r="24"
            fill="none"
            stroke={cfg.borderVar}
            strokeWidth="0.8"
            strokeDasharray="2 1.5"
          />
          <text
            x="32"
            y="35"
            textAnchor="middle"
            fill={cfg.colorVar}
            fontFamily="var(--font-mono), monospace"
            fontSize="8.5"
            fontWeight="700"
            letterSpacing="0.08em"
          >
            {text.slice(0, 9)}
          </text>
        </svg>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center justify-center rounded-xs border font-mono font-bold uppercase tracking-[0.09em] select-none shrink-0 ${
        size === "md" ? "px-2.5 py-1 text-[11px] border-[1.5px]" : "px-1.5 py-0.5 text-[10px]"
      } ${animate ? "animate-stamp-drop" : "-rotate-1"} ${className}`}
      style={{
        color: cfg.colorVar,
        borderColor: cfg.borderVar,
        backgroundColor: cfg.bgVar,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${cfg.borderVar} 30%, transparent)`,
      }}
    >
      {text}
    </span>
  );
}
