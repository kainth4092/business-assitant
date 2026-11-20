"use client";

import React, { useState, useEffect } from "react";
import { Database, FileText, CheckCircle2, Compass, Layers } from "lucide-react";

const STEPS = [
  { name: "Routing question intent & selecting tools...", icon: Compass },
  { name: "Executing read-only SQL on PostgreSQL sales table...", icon: Database },
  { name: "Retrieving semantic document embeddings via pgvector...", icon: FileText },
  { name: "Synthesizing answer with verified inline citations...", icon: Layers },
  { name: "Running factual groundedness check (retry cap 2)...", icon: CheckCircle2 }
];

export default function StatusLine({ isLoading }) {
  const [currentStepIdx, setCurrentStepIdx] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      setCurrentStepIdx(0);
      return;
    }
    const interval = setInterval(() => {
      setCurrentStepIdx((prev) => (prev + 1) % STEPS.length);
    }, 1400);
    return () => clearInterval(interval);
  }, [isLoading]);

  if (!isLoading) return null;

  const currentStep = STEPS[currentStepIdx];
  const StepIcon = currentStep.icon;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded bg-surface border border shadow-card text-xs font-mono my-2 animate-fade-up">
      {/* Soft pulse node (no bouncing dots) */}
      <div className="relative flex items-center justify-center shrink-0">
        <span className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse-soft" />
        <span className="absolute w-4 h-4 rounded-full bg-accent/20 animate-ping" />
      </div>

      <StepIcon className="w-3.5 h-3.5 text-accent stroke-[2.2] shrink-0" />

      <span className="text-ink font-semibold truncate">
        {currentStep.name}
      </span>

      <span className="text-muted text-[11px] ml-auto font-bold tabular-nums shrink-0">
        Step {currentStepIdx + 1} of {STEPS.length}
      </span>
    </div>
  );
}
