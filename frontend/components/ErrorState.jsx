"use client";

import React from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

export default function ErrorState({
  title = "Unable to load data",
  message = "Check that the backend API is running and reachable.",
  onRetry = null,
  retryLabel = "Retry",
}) {
  return (
    <div
      role="alert"
      className="border border-seal bg-raised p-4 sm:p-5 rounded-xs paper-stack flex flex-col sm:flex-row sm:items-center justify-between gap-3"
    >
      <div className="flex items-start gap-3 min-w-0">
        <AlertTriangle
          className="w-4 h-4 shrink-0 mt-0.5 text-seal-ink"
          strokeWidth={1.6}
        />
        <div className="min-w-0 space-y-1">
          <div className="font-mono text-xs font-bold uppercase tracking-wider text-seal-ink">
            {title}
          </div>
          <p className="text-xs text-ink leading-relaxed break-words">
            {message}
          </p>
        </div>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xs border border-seal bg-seal text-seal-on font-mono text-xs font-bold hover:opacity-90 transition-opacity shrink-0 cursor-pointer"
        >
          <RotateCw className="w-3.5 h-3.5" strokeWidth={1.6} />
          <span>{retryLabel}</span>
        </button>
      )}
    </div>
  );
}
