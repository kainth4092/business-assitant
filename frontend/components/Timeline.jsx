"use client";

import React, { useState, useEffect } from "react";
import { Check, Minus, AlertCircle } from "lucide-react";

const LIVE_STEP_SEQUENCE = [
  { id: "route", name: "Route", detail: "Classifying intent (DATA / DOCS / BOTH)" },
  { id: "query", name: "Query", detail: "Validating and executing read-only SQL" },
  { id: "retrieve", name: "Retrieve", detail: "Searching vector chunks in pgvector" },
  { id: "answer", name: "Answer", detail: "Drafting response with inline citations" },
  { id: "check", name: "Check", detail: "Verifying factual groundedness" },
];

export default function Timeline({
  steps = null,
  trace = {},
  toolsUsed = [],
  mode = "vertical", // "vertical" | "horizontal"
  isLoading = false,
  activeLiveStep = null,
  liveMessage = null,
}) {
  const [tickIdx, setTickIdx] = useState(0);

  useEffect(() => {
    if (!isLoading || activeLiveStep) return;
    const timer = setInterval(() => {
      setTickIdx((prev) => (prev + 1) % LIVE_STEP_SEQUENCE.length);
    }, 1300);
    return () => clearInterval(timer);
  }, [isLoading, activeLiveStep]);

  const effectiveTickIdx = isLoading ? tickIdx : 0;

  const route =
    trace?.route ||
    (toolsUsed.includes("query_sales") && toolsUsed.includes("search_docs")
      ? "both"
      : toolsUsed.includes("query_sales")
      ? "data"
      : "docs");

  const hasSql =
    !isLoading && toolsUsed.length > 0
      ? toolsUsed.includes("query_sales")
      : toolsUsed.includes("query_sales") || route === "data" || route === "both";
  const hasDocs =
    !isLoading && toolsUsed.length > 0
      ? toolsUsed.includes("search_docs")
      : toolsUsed.includes("search_docs") || route === "docs" || route === "both";
  const isGrounded = trace?.is_grounded ?? true;
  const retries = trace?.retries ?? 0;

  const computedSteps =
    steps ||
    LIVE_STEP_SEQUENCE.map((s, idx) => {
      if (isLoading) {
        const activeIdx = activeLiveStep
          ? Math.max(0, LIVE_STEP_SEQUENCE.findIndex((item) => item.id === activeLiveStep))
          : effectiveTickIdx;
        const status = idx < activeIdx ? "done" : idx === activeIdx ? "active" : "pending";
        return {
          ...s,
          status,
          desc:
            idx === activeIdx && liveMessage
              ? liveMessage
              : s.detail,
        };
      }

      if (s.id === "route") {
        return { ...s, status: "done", desc: `Routed to [${route.toUpperCase()}]` };
      }
      if (s.id === "query") {
        return {
          ...s,
          status: hasSql ? "done" : "bypassed",
          desc: hasSql ? "Executed read-only SELECT" : "Bypassed",
        };
      }
      if (s.id === "retrieve") {
        return {
          ...s,
          status: hasDocs ? "done" : "bypassed",
          desc: hasDocs ? "Retrieved pgvector chunks" : "Bypassed",
        };
      }
      if (s.id === "answer") {
        return { ...s, status: "done", desc: "Synthesized grounded log entry" };
      }
      return {
        ...s,
        status: isGrounded ? "done" : "failed",
        desc: isGrounded ? `Verified (${retries}/2 retries)` : "Flagged for review",
      };
    });

  const activeStepObj = computedSteps.find((s) => s.status === "active") || computedSteps[0];

  if (mode === "horizontal") {
    return (
      <div
        className="border border-grid rounded-xs bg-raised p-3 paper-stack space-y-2.5"
        role="status"
        aria-live="polite"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-wider text-ink">
            <span className="inline-block w-2 h-2 rounded-xs bg-highlighter border border-ink" />
            <span>{isLoading ? `Running: ${activeStepObj.name}` : "Pipeline Complete"}</span>
          </div>
          <span className="font-mono text-[11px] text-muted truncate">
            {liveMessage || activeStepObj.desc}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
          {computedSteps.map((st, idx) => {
            const isActive = st.status === "active";
            const isDone = st.status === "done";
            const isBypassed = st.status === "bypassed";
            return (
              <div
                key={st.id}
                className={`relative overflow-hidden border rounded-xs px-2.5 py-1.5 ${
                  isActive
                    ? "border-ink bg-raised"
                    : isDone
                    ? "border-grid bg-sunken/70"
                    : "border-grid bg-paper/60 opacity-75"
                }`}
              >
                {isActive && (
                  <span
                    aria-hidden="true"
                    className="absolute inset-0 bg-highlighter-wash animate-highlighter-stroke"
                  />
                )}
                <div className="relative flex items-center justify-between gap-1 font-mono text-[10px]">
                  <span className="font-bold text-ink uppercase">
                    0{idx + 1} {st.name}
                  </span>
                  {isDone && <Check className="w-3 h-3 text-sage-ink" strokeWidth={1.8} />}
                  {isBypassed && <Minus className="w-3 h-3 text-muted" strokeWidth={1.6} />}
                </div>
                <div className="relative font-mono text-[9.5px] text-muted truncate mt-0.5">
                  {st.desc}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <ol className="space-y-2 relative" aria-label="Agent execution steps">
      {computedSteps.map((st, idx) => {
        const isActive = st.status === "active";
        const isDone = st.status === "done";
        const isFailed = st.status === "failed";
        const isBypassed = st.status === "bypassed";

        return (
          <li
            key={st.id}
            className={`relative border rounded-xs px-3 py-2 overflow-hidden transition-colors ${
              isActive
                ? "border-ink bg-raised"
                : isFailed
                ? "border-seal bg-seal-tint"
                : isBypassed
                ? "border-grid/70 bg-paper/40 opacity-75"
                : "border-grid bg-raised"
            }`}
          >
            {isActive && (
              <span
                aria-hidden="true"
                className="absolute inset-0 bg-highlighter-wash animate-highlighter-stroke"
              />
            )}
            <div className="relative flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[10px] font-bold text-muted tabular-mono shrink-0">
                  0{idx + 1}
                </span>
                <span
                  className={`font-mono text-xs font-bold uppercase tracking-wider truncate ${
                    isActive ? "marker-stroke text-ink" : "text-ink"
                  }`}
                >
                  {st.name}
                </span>
              </div>
              <span className="font-mono text-[10px] font-semibold shrink-0 flex items-center gap-1">
                {isDone && (
                  <span className="text-sage-ink inline-flex items-center gap-1">
                    <Check className="w-3 h-3" strokeWidth={1.8} />
                    OK
                  </span>
                )}
                {isActive && <span className="text-ink font-bold">ACTIVE</span>}
                {isBypassed && <span className="text-muted">SKIP</span>}
                {isFailed && (
                  <span className="text-seal-ink inline-flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" strokeWidth={1.8} />
                    CHECK
                  </span>
                )}
                {st.status === "pending" && <span className="text-muted">WAIT</span>}
              </span>
            </div>
            <p className="relative font-mono text-[11px] text-muted mt-1 leading-snug break-words">
              {st.desc}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
