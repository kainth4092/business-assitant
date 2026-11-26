"use client";

import React from "react";

export function SkeletonLine({ className = "h-3 w-full" }) {
  return (
    <div
      className={`skeleton-paper rounded-xs border border-grid/50 ${className}`}
      aria-hidden="true"
    />
  );
}

export function SkeletonTable({ rows = 4, cols = 4 }) {
  return (
    <div
      className="border border-grid rounded-xs bg-raised overflow-hidden"
      aria-busy="true"
      aria-label="Loading table data"
    >
      <div className="px-3 py-2 border-b border-grid bg-sunken flex gap-3">
        {Array.from({ length: cols }).map((_, idx) => (
          <SkeletonLine key={idx} className="h-3 flex-1" />
        ))}
      </div>
      <div className="divide-y divide-grid">
        {Array.from({ length: rows }).map((_, rIdx) => (
          <div key={rIdx} className="px-3 py-2.5 flex gap-3">
            {Array.from({ length: cols }).map((_, cIdx) => (
              <SkeletonLine
                key={cIdx}
                className={`h-3 flex-1 ${cIdx === 0 ? "max-w-[90px]" : ""}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonStripList({ count = 4 }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading strips">
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="p-3 border border-grid rounded-xs bg-raised space-y-2"
        >
          <div className="flex items-center justify-between gap-2">
            <SkeletonLine className="h-3 w-24" />
            <SkeletonLine className="h-3 w-16" />
          </div>
          <SkeletonLine className="h-4 w-3/4" />
          <div className="flex items-center justify-between gap-2">
            <SkeletonLine className="h-2.5 w-32" />
            <SkeletonLine className="h-2.5 w-10" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Skeleton({ variant = "table", ...props }) {
  if (variant === "strips") return <SkeletonStripList {...props} />;
  if (variant === "line") return <SkeletonLine {...props} />;
  return <SkeletonTable {...props} />;
}
