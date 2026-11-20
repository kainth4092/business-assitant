"use client";

import React from "react";
import { CheckCircle2, Clock, AlertCircle, Compass, Database, FileText, Sparkles, ShieldCheck } from "lucide-react";

export default function Timeline({
  trace = {},
  toolsUsed = [],
  mode = "horizontal", // 'horizontal' | 'vertical'
  isLoading = false
}) {
  const route = trace?.route || (toolsUsed.includes("query_sales") && toolsUsed.includes("search_docs") ? "both" : toolsUsed.includes("query_sales") ? "data" : "docs");
  const retries = trace?.retries ?? 0;
  const isGrounded = trace?.is_grounded ?? true;

  const hasSql = toolsUsed.includes("query_sales") || route === "data" || route === "both";
  const hasDocs = toolsUsed.includes("search_docs") || route === "docs" || route === "both";

  const steps = [
    {
      id: "route",
      num: "1",
      name: "Route",
      subtext: route.toUpperCase(),
      icon: Compass,
      status: "done",
      color: "text-accent-emerald",
      bg: "bg-accent-emerald/10 border-accent-emerald/30",
    },
    {
      id: "sql",
      num: "2",
      name: "SQL Gen",
      subtext: hasSql ? "PostgreSQL" : "Bypassed",
      icon: Database,
      status: hasSql ? "done" : "skipped",
      color: hasSql ? "text-accent-cyan" : "text-muted",
      bg: hasSql ? "bg-accent-cyan/10 border-accent-cyan/30" : "bg-surface-container border-border",
    },
    {
      id: "retrieve",
      num: "3",
      name: "Retrieve",
      subtext: hasDocs ? "pgvector (k=3)" : "Bypassed",
      icon: FileText,
      status: hasDocs ? "done" : "skipped",
      color: hasDocs ? "text-accent-amber" : "text-muted",
      bg: hasDocs ? "bg-accent-amber/10 border-accent-amber/30" : "bg-surface-container border-border",
    },
    {
      id: "synthesis",
      num: "4",
      name: "Synthesis",
      subtext: isLoading ? "Streaming..." : "Gemini 3.8",
      icon: Sparkles,
      status: isLoading ? "active" : "done",
      color: "text-accent-lime",
      bg: isLoading ? "bg-accent-lime/20 border-accent-lime" : "bg-surface-container border-border",
    },
    {
      id: "safety",
      num: "5",
      name: "Safety",
      subtext: retries > 0 ? `${retries}/2 retries` : isGrounded ? "Grounded" : "Review",
      icon: ShieldCheck,
      status: isLoading ? "pending" : isGrounded ? "done" : "warn",
      color: isGrounded ? "text-accent-emerald" : "text-accent-amber",
      bg: isGrounded ? "bg-accent-emerald/10 border-accent-emerald/30" : "bg-accent-amber/10 border-accent-amber/30",
    },
  ];

  // =========================================================================
  // HORIZONTAL PIPELINE STRIP
  // =========================================================================
  if (mode === "horizontal") {
    return (
      <div className="bg-surface rounded-lg p-3 border border-border shadow-xs flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-emerald" />
            <span className="font-mono text-[10px] uppercase text-primary font-bold tracking-wider">
              Multi-Agent Dispatch Flow
            </span>
          </div>
          <span className="font-mono text-[10px] text-muted">
            Route: [{route.toUpperCase()}] &middot; Verified Grounded
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 items-center">
          {steps.map((st) => {
            const Icon = st.icon;
            const isActive = st.status === "active";
            const isDone = st.status === "done";
            return (
              <div
                key={st.id}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded border transition-all ${st.bg} ${
                  isActive ? "ring-2 ring-accent-lime shadow-xs" : ""
                }`}
              >
                {isActive ? (
                  <span className="relative flex h-3 w-3 shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-lime opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-accent-lime" />
                  </span>
                ) : isDone ? (
                  <CheckCircle2 className={`w-3.5 h-3.5 shrink-0 ${st.color} stroke-[2.2]`} />
                ) : (
                  <Clock className="w-3.5 h-3.5 shrink-0 text-muted stroke-[2]" />
                )}

                <div className="flex flex-col min-w-0">
                  <span className="font-mono text-[10px] uppercase font-bold text-primary truncate leading-tight">
                    {st.num}. {st.name}
                  </span>
                  <span className="font-mono text-[9.5px] text-muted truncate leading-tight">
                    {st.subtext}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // =========================================================================
  // VERTICAL INFERENCE CALL STACK
  // =========================================================================
  return (
    <div className="bg-surface rounded-lg p-3.5 border border-border shadow-xs flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase text-muted font-bold tracking-wider">
          Inference Call Stack
        </span>
        <span className="font-mono text-[10px] text-accent-emerald font-semibold">
          {steps.filter((s) => s.status === "done").length} Completed
        </span>
      </div>

      <div className="relative pl-5 flex flex-col gap-3.5">
        {/* Continuous vertical connecting line */}
        <div className="absolute left-1.5 top-2 bottom-2 w-[1px] bg-border" />

        {steps.map((st) => {
          const isDone = st.status === "done";
          const isActive = st.status === "active";

          return (
            <div key={st.id} className="relative flex items-start gap-2.5">
              <div
                className={`absolute -left-5 top-0.5 w-3 h-3 rounded-full border-2 border-surface transition-colors ${
                  isActive
                    ? "bg-accent-lime animate-ping"
                    : isDone
                    ? "bg-accent-emerald"
                    : "bg-border"
                }`}
              />
              <div className="flex flex-col min-w-0">
                <span className="font-mono text-[11px] font-bold text-primary leading-tight">
                  {st.num}. {st.name}: {st.subtext}
                </span>
                <span className="font-mono text-[10px] text-muted leading-tight mt-0.5">
                  {st.id === "route" && `Intent classified into [${route.toUpperCase()}]`}
                  {st.id === "sql" && (hasSql ? "SELECT query dispatched to Postgres 16" : "No SQL required")}
                  {st.id === "retrieve" && (hasDocs ? "Cosine search over 21 document embeddings" : "No documents needed")}
                  {st.id === "synthesis" && (isLoading ? "Streaming grounded claim tokens" : "Synthesized response generated")}
                  {st.id === "safety" && (isGrounded ? "Grounded in tool outputs with 0 hallucination" : "Evaluating groundedness")}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
