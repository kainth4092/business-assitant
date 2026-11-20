"use client";

import React, { useState, useEffect } from "react";
import { Database, FileText, Wrench, RotateCw, AlertCircle } from "lucide-react";
import StatTile from "./StatTile";
import StarterRow from "./StarterRow";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function EmptyState({ onSelectQuery = () => {}, systemHealth = null }) {
  const [starters, setStarters] = useState([]);
  const [isLoadingStarters, setIsLoadingStarters] = useState(true);
  const [starterError, setStarterError] = useState(null);

  const fetchSampleQuestions = async () => {
    setIsLoadingStarters(true);
    setStarterError(null);
    try {
      const res = await fetch(`${API_BASE}/sample-questions`);
      if (res.ok) {
        const data = await res.json();
        setStarters(data.starters || []);
      } else {
        throw new Error(`Failed to fetch sample starters (HTTP ${res.status})`);
      }
    } catch (err) {
      console.warn("Could not load dynamic sample questions:", err);
      setStarterError(err.message);
    } finally {
      setIsLoadingStarters(false);
    }
  };

  useEffect(() => {
    fetchSampleQuestions();
  }, []);

  const salesCount = systemHealth?.sales_records ?? null;
  const chunksCount = systemHealth?.indexed_chunks ?? null;
  const toolsCount = systemHealth?.tools_count ?? systemHealth?.tools?.length ?? null;

  return (
    <div className="py-1 sm:py-2 w-full max-w-4xl mx-auto space-y-4 pb-2 animate-fade-up">
      {/* Editorial Header */}
      <div className="space-y-1.5 border-b border-border pb-3.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-label-telemetry uppercase text-accent-cyan font-bold tracking-wider">
            Enterprise Analytical System
          </span>
          <span className="text-muted text-xs">&middot;</span>
          <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
            Autonomous Routing
          </span>
        </div>

        <h1 className="font-headline text-[24px] sm:text-[28px] text-primary font-bold tracking-tight leading-tight">
          Investigate sales metrics &amp; company policies
        </h1>

        <p className="font-body text-body-sm sm:text-body-md text-muted leading-relaxed max-w-3xl">
          The Business Assistant autonomously inspects structured PostgreSQL sales records via read-only SQL, searches vectorized operational manuals in pgvector, or unifies both into a verified, citation-grounded answer.
        </p>
      </div>

      {/* 3 Telemetry Metrics Deck (Strictly Live API Data) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatTile
          icon={Database}
          value={salesCount !== null ? salesCount : "..."}
          label="Cleaned sales rows"
          accent="cyan"
          badge="PG_SALES"
        />
        <StatTile
          icon={FileText}
          value={chunksCount !== null ? chunksCount : "..."}
          label="pgvector policy chunks"
          accent="amber"
          badge="HNSW"
        />
        <StatTile
          icon={Wrench}
          value={toolsCount !== null ? toolsCount : "..."}
          label="MCP Tools Suite"
          accent="lime"
          badge="ACTIVE"
        />
      </div>

      {/* Dynamic Investigation Starters (Generated from Real Data) */}
      <div className="space-y-2 pt-1">
        <div className="flex items-center justify-between pb-0.5">
          <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
            Preset Investigation Starters
          </span>
          <span className="font-mono text-label-telemetry text-muted">
            Click any row to execute
          </span>
        </div>

        {isLoadingStarters ? (
          <div className="p-8 rounded-lg border border-border bg-surface flex flex-col items-center justify-center gap-2 text-muted text-xs font-mono">
            <RotateCw className="w-5 h-5 animate-spin text-accent-cyan" />
            <span>Generating questions dynamically from PostgreSQL &amp; pgvector...</span>
          </div>
        ) : starterError ? (
          <div className="p-4 rounded-lg border border-accent-amber/30 bg-accent-amber/10 flex items-center justify-between text-xs font-mono text-accent-amber">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Could not load sample starters. Ensure backend is running.</span>
            </div>
            <button
              onClick={fetchSampleQuestions}
              className="px-2.5 py-1 rounded bg-accent-amber text-black font-bold text-[11px]"
            >
              Retry
            </button>
          </div>
        ) : starters.length === 0 ? (
          <div className="p-6 text-center border border-border rounded-lg bg-surface text-muted text-xs font-mono">
            No questions generated yet. Run the ingestion pipeline to index documents and load sales records.
          </div>
        ) : (
          <div className="space-y-2">
            {starters.map((s, idx) => (
              <StarterRow
                key={s.num || idx}
                index={idx}
                num={s.num || String(idx + 1).padStart(2, "0")}
                query={s.query}
                caption={s.caption}
                route={s.route}
                onSelect={(q, r) => onSelectQuery(q, r)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
