"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";
import AddDataArea from "./AddDataArea";

export default function AddDataModal({ isOpen, onClose, onPipelineComplete }) {
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/45"
      role="dialog"
      aria-modal="true"
      aria-label="Add data and run pipeline"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-xs border border-ink bg-paper p-4 paper-stack-strong"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-end mb-2">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xs border border-grid bg-raised text-muted hover:text-ink cursor-pointer"
            aria-label="Close upload dialog"
          >
            <X className="w-4 h-4" strokeWidth={1.6} />
          </button>
        </div>
        <AddDataArea
          onPipelineComplete={() => {
            onPipelineComplete();
            onClose();
          }}
        />
      </div>
    </div>
  );
}
