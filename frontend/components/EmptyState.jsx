"use client";

import React, { useState, useEffect } from "react";
import { ArrowRight, Check, Plus, Database, FileText, Layers } from "lucide-react";
import AddDataArea from "./AddDataArea";
import ErrorState from "./ErrorState";
import Skeleton from "./Skeleton";
import { getRouteMeta } from "../lib/formatters";
import { useCountUpOnce } from "../lib/useCountUp";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function EmptyState({
  onSelectQuery = () => {},
  systemHealth = null,
  isStatusLoading = false,
  statusError = null,
  onRetryStatus = () => {},
  onDataRefresh = () => {},
}) {
  const [starters, setStarters] = useState([]);
  const [isLoadingStarters, setIsLoadingStarters] = useState(true);
  const [starterError, setStarterError] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [showUploader, setShowUploader] = useState(false);

  const loadSampleQuestions = async (showSpinner = false) => {
    if (showSpinner) setIsLoadingStarters(true);
    setStarterError(null);
    try {
      const res = await fetch(`${API_BASE}/sample-questions`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status} loading starters`);
      }
      const data = await res.json();
      setStarters(data.starters || []);
    } catch (err) {
      setStarterError(err.message || "Could not load sample questions.");
    } finally {
      setIsLoadingStarters(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/sample-questions`);
        if (cancelled) return;
        if (!res.ok) {
          throw new Error(`HTTP ${res.status} loading starters`);
        }
        const data = await res.json();
        if (!cancelled) setStarters(data.starters || []);
      } catch (err) {
        if (!cancelled) {
          setStarterError(err.message || "Could not load sample questions.");
        }
      } finally {
        if (!cancelled) setIsLoadingStarters(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const salesCount = systemHealth?.sales_records ?? 0;
  const chunksCount = systemHealth?.indexed_chunks ?? 0;
  const toolsCount = systemHealth?.tools_count ?? systemHealth?.tools?.length ?? 0;

  const animSales = useCountUpOnce(salesCount, 500);
  const animChunks = useCountUpOnce(chunksCount, 500);
  const animTools = useCountUpOnce(toolsCount, 500);

  if (isStatusLoading && !systemHealth) {
    return (
      <div className="w-full max-w-4xl mx-auto py-3 space-y-4">
        <Skeleton variant="strips" count={3} />
      </div>
    );
  }

  if (!systemHealth && statusError) {
    return (
      <div className="w-full max-w-4xl mx-auto py-3">
        <ErrorState
          title="Backend Connection Unavailable"
          message={statusError}
          onRetry={() => {
            onRetryStatus();
            loadSampleQuestions(true);
          }}
        />
      </div>
    );
  }

  const isZeroState = systemHealth !== null && salesCount === 0 && chunksCount === 0;

  const handlePipelineCompleted = () => {
    loadSampleQuestions(true);
    onDataRefresh();
  };

  // First-run onboarding when database has zero rows and zero chunks
  if (isZeroState) {
    const step1Done = Boolean(pipelineStatus?.has_csv);
    const step2Done = Boolean(pipelineStatus?.has_documents || chunksCount > 0);
    const step3Done = salesCount > 0 || chunksCount > 0;

    const steps = [
      {
        num: "01",
        label: "Upload a CSV",
        status: step1Done
          ? `Staged: ${pipelineStatus?.primary_csv || "CSV ready"}`
          : "Pending",
        done: step1Done,
      },
      {
        num: "02",
        label: "Add documents",
        status: step2Done
          ? `${pipelineStatus?.documents_count || 1} document(s) staged`
          : "Optional · .md, .txt, .pdf",
        done: step2Done,
      },
      {
        num: "03",
        label: "Run the pipeline",
        status: step3Done
          ? "Loaded into PostgreSQL"
          : step1Done || step2Done
          ? "Ready to run"
          : "Waiting for files",
        done: step3Done,
      },
    ];

    return (
      <div className="w-full max-w-4xl mx-auto py-3 space-y-5">
        <section className="border border-grid rounded-xs bg-raised p-5 paper-stack space-y-4">
          <div className="space-y-1 border-b border-grid pb-3">
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted font-bold">
              First-Run Onboarding
            </div>
            <h1 className="font-serif text-2xl sm:text-3xl font-semibold text-ink">
              Upload a CSV to begin
            </h1>
            <p className="text-xs sm:text-sm text-muted leading-relaxed max-w-2xl">
              The workbench has no dataset or indexed policy documents yet. Follow the checklist below to ingest data into PostgreSQL and pgvector.
            </p>
          </div>

          <ol className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {steps.map((st) => (
              <li
                key={st.num}
                className={`p-3 rounded-xs border ${
                  st.done
                    ? "border-sage bg-sage-tint"
                    : "border-grid bg-paper/70"
                }`}
              >
                <div className="flex items-center justify-between font-mono text-[10.5px]">
                  <span className="font-bold text-ink">{st.num}</span>
                  {st.done ? (
                    <span className="inline-flex items-center gap-1 text-sage-ink font-bold">
                      <Check className="w-3 h-3" strokeWidth={1.8} />
                      READY
                    </span>
                  ) : (
                    <span className="text-muted">WAIT</span>
                  )}
                </div>
                <div className="font-serif text-sm font-semibold text-ink mt-1">
                  {st.label}
                </div>
                <div className="font-mono text-[10.5px] text-muted mt-0.5 truncate">
                  {st.status}
                </div>
              </li>
            ))}
          </ol>
        </section>

        <AddDataArea
          onPipelineComplete={handlePipelineCompleted}
          onStatusChange={setPipelineStatus}
        />
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto py-2 space-y-5">
      {/* Header & Live Telemetry Strip */}
      <section className="border border-grid rounded-xs bg-raised p-4 sm:p-5 paper-stack space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-grid pb-3">
          <div className="space-y-1">
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted font-bold">
              Operations Logbook · Live Query Desk
            </div>
            <h1 className="font-serif text-2xl sm:text-3xl font-semibold text-ink leading-tight">
              Query structured data &amp; policy manuals
            </h1>
          </div>

          <button
            type="button"
            onClick={() => setShowUploader(!showUploader)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xs border border-grid bg-paper text-ink hover:border-ink font-mono text-xs font-semibold cursor-pointer shrink-0"
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={1.6} />
            <span>{showUploader ? "Hide Intake" : "Add Data"}</span>
          </button>
        </div>

        <div className="grid grid-cols-3 gap-2.5">
          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold truncate">
              Sales Rows
            </div>
            <div className="font-mono text-xl sm:text-2xl font-bold text-route-data-ink tabular-mono mt-0.5">
              {animSales.toLocaleString()}
            </div>
          </div>

          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold truncate">
              Vector Chunks
            </div>
            <div className="font-mono text-xl sm:text-2xl font-bold text-route-docs-ink tabular-mono mt-0.5">
              {animChunks.toLocaleString()}
            </div>
          </div>

          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold truncate">
              MCP Tools
            </div>
            <div className="font-mono text-xl sm:text-2xl font-bold text-ink tabular-mono mt-0.5">
              {animTools.toLocaleString()}
            </div>
          </div>
        </div>
      </section>

      {showUploader && (
        <AddDataArea
          isCompact
          onPipelineComplete={handlePipelineCompleted}
          onStatusChange={setPipelineStatus}
        />
      )}

      {/* Dynamic Starter Questions */}
      <section className="space-y-2.5">
        <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-wider text-muted font-bold">
          <span>Suggested Inquiries (From Live Schema)</span>
          <span>Select to run</span>
        </div>

        {isLoadingStarters ? (
          <Skeleton variant="strips" count={3} />
        ) : starterError ? (
          <ErrorState
            title="Could Not Load Starters"
            message={starterError}
            onRetry={() => loadSampleQuestions(true)}
          />
        ) : starters.length === 0 ? (
          <div className="p-4 border border-grid rounded-xs bg-raised font-mono text-xs text-muted">
            No suggested inquiries generated yet. Type any question below to begin.
          </div>
        ) : (
          <div className="divide-y divide-grid border border-grid rounded-xs bg-raised paper-stack">
            {starters.map((s, idx) => {
              const rMeta = getRouteMeta(s.route);
              const RIcon =
                rMeta.key === "data"
                  ? Database
                  : rMeta.key === "both"
                  ? Layers
                  : FileText;
              return (
                <button
                  key={s.num || idx}
                  type="button"
                  onClick={() => onSelectQuery(s.query, s.route)}
                  className="w-full text-left px-4 py-3 hover:bg-highlighter-wash/70 transition-colors flex items-center justify-between gap-3 cursor-pointer group"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <span className="font-mono text-xs font-bold text-muted tabular-mono pt-0.5 shrink-0">
                      {s.num || String(idx + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 space-y-0.5">
                      <div className="font-serif text-sm sm:text-base font-semibold text-ink leading-snug break-words">
                        {s.query}
                      </div>
                      {s.caption && (
                        <div className="font-sans text-xs text-muted line-clamp-1">
                          {s.caption}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-xs border font-mono text-[10px] font-bold uppercase"
                      style={{
                        color: rMeta.inkVar,
                        borderColor: rMeta.colorVar,
                        backgroundColor: rMeta.tintVar,
                      }}
                    >
                      <RIcon className="w-3 h-3" strokeWidth={1.6} />
                      <span>{rMeta.label}</span>
                    </span>
                    <ArrowRight
                      className="w-4 h-4 text-muted group-hover:text-ink group-hover:translate-x-0.5 transition-transform"
                      strokeWidth={1.6}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
