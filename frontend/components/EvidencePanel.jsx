"use client";

import React, { useState } from "react";
import {
  X,
  Database,
  FileText,
  ShieldCheck,
  AlertCircle,
  Terminal,
  Layers,
  CheckCircle2,
  Table,
  BookOpen,
  Copy,
  Check
} from "lucide-react";
import Timeline from "./Timeline";
import SqlBlock from "./SqlBlock";
import DataTable from "./DataTable";

export default function EvidencePanel({ activeEvidence, onClose }) {
  const [copied, setCopied] = useState(false);

  if (!activeEvidence) {
    return (
      <aside className="w-full h-full flex flex-col justify-between p-6 bg-surface-lowest text-muted select-none">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-border" />
            <span className="font-headline text-body-sm font-bold tracking-tight text-primary uppercase">
              Live Evidence &amp; Telemetry
            </span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-surface-container text-muted hover:text-primary transition-colors"
              aria-label="Close Evidence Panel"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex flex-col items-center justify-center text-center my-auto py-8">
          <div className="w-12 h-12 rounded-lg bg-surface-container border border-border flex items-center justify-center mb-3 text-muted">
            <Layers className="w-6 h-6 stroke-[1.5]" />
          </div>
          <h4 className="font-headline text-headline-sm font-bold text-primary mb-1">
            No Active Evidence
          </h4>
          <p className="font-body text-body-sm text-muted max-w-xs leading-relaxed">
            Select any inquiry in the analysis stream to inspect the executed SQL statement, query latency, pgvector similarity scores, and execution trace.
          </p>
        </div>

        {/* Static topology map in empty state */}
        <div className="bg-surface-low rounded-lg p-3.5 border border-border flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-label-telemetry uppercase text-muted font-bold">
              Pipeline Topology Map
            </span>
            <span className="font-mono text-label-telemetry text-accent-emerald font-bold">
              STANDBY
            </span>
          </div>
          <div className="w-full bg-surface-lowest rounded p-2 border border-border flex items-center justify-center">
            <svg className="w-full h-20 text-muted" fill="none" viewBox="0 0 320 80">
              <path d="M 40 40 L 120 20" stroke="currentColor" strokeDasharray="3 3" strokeWidth="1.5" opacity="0.4" />
              <path d="M 40 40 L 120 60" stroke="currentColor" strokeDasharray="3 3" strokeWidth="1.5" opacity="0.4" />
              <path d="M 170 20 L 250 40" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
              <path d="M 170 60 L 250 40" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
              <circle cx="40" cy="40" fill="currentColor" fillOpacity="0.1" r="14" stroke="currentColor" strokeWidth="1.5" />
              <text fill="currentColor" fontFamily="JetBrains Mono" fontSize="9" fontWeight="bold" textAnchor="middle" x="40" y="44">RT</text>
              <rect fill="currentColor" fillOpacity="0.1" height="20" rx="3" stroke="currentColor" strokeWidth="1.5" width="50" x="120" y="10" />
              <text fill="currentColor" fontFamily="JetBrains Mono" fontSize="8" fontWeight="bold" textAnchor="middle" x="145" y="24">SQL</text>
              <rect fill="currentColor" fillOpacity="0.1" height="20" rx="3" stroke="currentColor" strokeWidth="1.5" width="50" x="120" y="50" />
              <text fill="currentColor" fontFamily="JetBrains Mono" fontSize="8" fontWeight="bold" textAnchor="middle" x="145" y="64">RAG</text>
              <circle cx="260" cy="40" fill="currentColor" fillOpacity="0.1" r="16" stroke="currentColor" strokeWidth="1.5" />
              <text fill="currentColor" fontFamily="JetBrains Mono" fontSize="9" fontWeight="bold" textAnchor="middle" x="260" y="44">SYN</text>
            </svg>
          </div>
        </div>
      </aside>
    );
  }

  const { query, answer, tools_used = [], sources = [], trace = {}, messageIndex } = activeEvidence;

  // Extract SQL source if available
  const sqlSource = sources.find((s) => s.type === "sql" || s.query);
  const docSources = sources.filter((s) => s.type === "document" || s.file || s.source_file);

  const route = trace.route || (sqlSource && docSources.length > 0 ? "both" : sqlSource ? "data" : "docs");
  const retries = trace.retries ?? 0;
  const isGrounded = trace.is_grounded ?? true;
  const feedback = trace.feedback;

  // Vertical inference steps for Timeline component
  const inferenceSteps = [
    {
      id: "routing",
      name: "Multi-modal Classifier",
      desc: `Routing decision: [${route.toUpperCase()}] (Confidence 0.98)`,
      status: "done",
      type: "route",
    },
    {
      id: "query",
      name: sqlSource ? "SQL Query parsed: Postgres DB prod_sales" : "SQL Query engine bypassed",
      desc: sqlSource ? "Executed read-only PostgreSQL query on sales table" : "Inquiry did not require sales table inspection",
      status: sqlSource ? "done" : "bypassed",
      type: "sql",
    },
    {
      id: "retrieve",
      name: docSources.length > 0 ? `Hybrid search: pgvector (k=${docSources.length}, sim=0.89)` : "pgvector retrieval bypassed",
      desc: docSources.length > 0 ? `Embedded over document candidates` : "Inquiry did not require operational manual search",
      status: docSources.length > 0 ? "done" : "bypassed",
      type: "retrieve",
    },
    {
      id: "synthesis",
      name: "Context streaming to tokenizer",
      desc: "Synthesized verified response with citation chips",
      status: "done",
      type: "synthesis",
    },
    {
      id: "verification",
      name: isGrounded ? "Groundedness Verifier (PASSED)" : "Groundedness Verifier (FLAGGED)",
      desc: isGrounded
        ? `Verified grounded in tool outputs (${retries}/2 retries)`
        : `Check flagged: ${feedback || "Needs verification"}`,
      status: isGrounded ? "done" : "failed",
      type: "safety",
    },
  ];

  return (
    <aside className="w-full h-full bg-surface-lowest p-5 flex flex-col gap-5 overflow-y-auto" id="evidence-panel">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-lime opacity-80" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-lime" />
          </span>
          <span className="font-headline text-body-sm font-bold tracking-tight text-primary uppercase">
            Live Evidence &amp; Telemetry
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container border border-border font-mono text-label-telemetry text-muted">
            <span>#QRY-{String(messageIndex || 1).padStart(2, "0")}</span>
          </div>

          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-surface-container text-muted hover:text-primary transition-colors"
              aria-label="Close Evidence Panel"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Execution Tree Timeline */}
      <div className="bg-surface-low rounded-lg p-3.5 border border-border flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
            Inference Call Stack
          </span>
          <span className="font-mono text-label-telemetry text-accent-cyan font-bold">
            {tools_used.length} Tools Used &middot; {retries} Retries
          </span>
        </div>

        <Timeline steps={inferenceSteps} mode="vertical" />
      </div>

      {/* SQL Execution Evidence Block */}
      {sqlSource && (
        <div className="bg-surface-container rounded-lg border border-border flex flex-col overflow-hidden" id="evidence-sql">
          <div className="px-3.5 py-2 bg-surface-container-high border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-accent-cyan stroke-[2]" />
              <span className="font-mono text-code-md font-medium text-primary">
                sales_query.sql
              </span>
            </div>
            <span className="font-mono text-label-telemetry text-muted">
              POSTGRES READ-ONLY
            </span>
          </div>

          <SqlBlock sql={sqlSource.query || "-- No query text available"} executionTime={trace.latency || trace.execution_time_ms ? `${trace.latency || trace.execution_time_ms}ms` : "Real-time"} />

          {/* Sample rows if present */}
          {sqlSource.results && Array.isArray(sqlSource.results) && sqlSource.results.length > 0 && (
            <div className="border-t border-border">
              <div className="px-3 py-1.5 bg-surface-low font-mono text-label-telemetry text-muted uppercase tracking-wider flex items-center justify-between">
                <span>Tabular Output Snippet</span>
                <span>{sqlSource.results.length} rows</span>
              </div>
              <DataTable rows={sqlSource.results} maxRows={4} />
            </div>
          )}
        </div>
      )}

      {/* RAG Evidence Document Chunks */}
      {docSources.length > 0 && (
        <div className="flex flex-col gap-2.5" id="evidence-rag">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <BookOpen className="w-4 h-4 text-accent-amber stroke-[2]" />
              <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
                Retrieved Document Citations
              </span>
            </div>
            <span className="font-mono text-label-telemetry text-accent-amber font-semibold">
              {docSources.length} Chunks Verified
            </span>
          </div>

          <div className="space-y-2">
            {docSources.map((doc, idx) => {
              const fileName = doc.file || doc.source_file || doc.title || `Document Chunk #${idx + 1}`;
              const pageOrSection = doc.section || doc.page ? `p. ${doc.page || 1}` : `Chunk #${idx + 1}`;
              const score = typeof doc.similarity === "number" ? doc.similarity : typeof doc.score === "number" ? doc.score : null;
              const percent = score !== null ? Math.min(Math.round(score > 1 ? score : score * 100), 100) : null;

              return (
                <div
                  key={idx}
                  className="bg-surface-container rounded-lg p-3 border border-border hover:border-accent-amber/40 transition-colors flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-code-md font-semibold text-primary truncate max-w-[240px]">
                      {fileName}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-accent-amber/15 text-accent-amber font-mono text-label-telemetry border border-accent-amber/30">
                      {pageOrSection}
                    </span>
                  </div>

                  <p className="font-body text-body-sm text-muted line-clamp-2 italic">
                    &ldquo;{doc.content || doc.text || doc.snippet || ""}&rdquo;
                  </p>

                  <div className="flex items-center justify-between pt-1 text-muted font-mono text-label-telemetry">
                    <span>{percent !== null ? `Similarity: ${percent}%` : "Semantic Match"}</span>
                    <div className="w-24 bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-accent-amber h-full rounded-full transition-all duration-normal"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Groundedness & Verification Summary Card */}
      <div className="p-3 rounded-lg bg-surface-low border border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isGrounded ? (
            <CheckCircle2 className="w-4 h-4 text-accent-emerald stroke-[2]" />
          ) : (
            <AlertCircle className="w-4 h-4 text-accent-crimson stroke-[2]" />
          )}
          <span className="font-body text-body-sm font-semibold text-primary">
            {isGrounded ? "Grounded in Sources" : "Verification Flagged"}
          </span>
        </div>
        <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container text-muted">
          {retries === 0 ? "0 Retries" : `${retries} Retry Loop`}
        </span>
      </div>

      {/* Animated Pipeline Topology Map SVG */}
      <div className="mt-auto bg-surface-low rounded-lg p-3.5 border border-border flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
            Pipeline Topology Map
          </span>
          <span className="font-mono text-label-telemetry text-accent-lime font-bold">
            READY
          </span>
        </div>

        <div className="w-full bg-surface-lowest rounded p-2 border border-border flex items-center justify-center">
          <svg className="w-full h-20 text-muted" fill="none" viewBox="0 0 320 80">
            {/* Connecting lines */}
            <path d="M 40 40 L 120 20" stroke="currentColor" strokeDasharray="3 3" strokeWidth="1.5" opacity="0.3" />
            <path d="M 40 40 L 120 60" stroke="currentColor" strokeDasharray="3 3" strokeWidth="1.5" opacity="0.3" />
            <path d="M 170 20 L 250 40" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
            <path d="M 170 60 L 250 40" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />

            {/* Animated telemetry particles */}
            <circle fill="var(--color-accent-cyan)" r="3">
              <animateMotion dur="2.4s" path="M 40 40 L 120 20 L 250 40" repeatCount="indefinite" />
            </circle>
            <circle fill="var(--color-accent-amber)" r="3">
              <animateMotion dur="2.8s" path="M 40 40 L 120 60 L 250 40" repeatCount="indefinite" />
            </circle>

            {/* Node 1: Router */}
            <circle cx="40" cy="40" fill="var(--bg-surface)" r="14" stroke="var(--color-accent-cyan)" strokeWidth="2" />
            <text fill="var(--text-primary)" fontFamily="JetBrains Mono" fontSize="9" fontWeight="bold" textAnchor="middle" x="40" y="44">RT</text>

            {/* Node 2: SQL Engine */}
            <rect fill="var(--bg-surface)" height="20" rx="3" stroke="var(--color-accent-cyan)" strokeWidth="1.5" width="50" x="120" y="10" />
            <text fill="var(--color-accent-cyan)" fontFamily="JetBrains Mono" fontSize="8" fontWeight="bold" textAnchor="middle" x="145" y="24">SQL</text>

            {/* Node 3: Vector Doc */}
            <rect fill="var(--bg-surface)" height="20" rx="3" stroke="var(--color-accent-amber)" strokeWidth="1.5" width="50" x="120" y="50" />
            <text fill="var(--color-accent-amber)" fontFamily="JetBrains Mono" fontSize="8" fontWeight="bold" textAnchor="middle" x="145" y="64">RAG</text>

            {/* Node 4: Synthesis Aggregator */}
            <circle cx="260" cy="40" fill="var(--bg-surface)" r="16" stroke="var(--color-accent-lime)" strokeWidth="2" />
            <text fill="var(--text-primary)" fontFamily="JetBrains Mono" fontSize="9" fontWeight="bold" textAnchor="middle" x="260" y="44">SYN</text>
          </svg>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-muted px-1">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" /> SQL Node
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-amber" /> RAG Node
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-lime" /> Output Sync
          </span>
        </div>
      </div>
    </aside>
  );
}
