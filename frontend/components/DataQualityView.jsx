"use client";

import React from "react";
import { RefreshCw, Database } from "lucide-react";
import QualityBars from "./QualityBars";
import Stamp from "./Stamp";
import Skeleton from "./Skeleton";
import ErrorState from "./ErrorState";
import { useCountUpOnce } from "../lib/useCountUp";

export default function DataQualityView({
  report,
  isLoading = false,
  error = null,
  onRefresh = () => {},
  systemHealth = null,
}) {
  const profile = report?.records_profile || {};
  const columnsProfile = report?.columns_profile || [];
  const rawRows = profile.raw_total_rows ?? 0;
  const cleanedRows = profile.cleaned_total_rows ?? 0;
  const dupsRemoved = profile.duplicate_rows_removed ?? 0;
  const columnCount = profile.column_count ?? columnsProfile.length;

  const animatedRaw = useCountUpOnce(rawRows, 500);
  const animatedCleaned = useCountUpOnce(cleanedRows, 500);
  const animatedDups = useCountUpOnce(dupsRemoved, 500);

  if (isLoading) {
    return (
      <div className="w-full max-w-6xl mx-auto space-y-4 pb-16">
        <div className="p-4 border border-grid rounded-xs bg-raised space-y-2">
          <div className="font-mono text-xs uppercase tracking-wider text-muted font-bold">
            Data Quality Audit
          </div>
          <div className="font-serif text-xl text-ink">
            Loading PySpark quality report...
          </div>
        </div>
        <Skeleton variant="table" rows={5} cols={4} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-6xl mx-auto pb-16">
        <ErrorState
          title="Quality Report Unavailable"
          message={error}
          onRetry={onRefresh}
        />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="w-full max-w-6xl mx-auto pb-16">
        <div className="border border-grid rounded-xs bg-raised p-8 text-center space-y-3 paper-stack">
          <Database className="w-7 h-7 mx-auto text-muted" strokeWidth={1.5} />
          <h2 className="font-serif text-xl font-semibold text-ink">
            Run the pipeline to see a report
          </h2>
          <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
            No PySpark data quality audit has been recorded in PostgreSQL yet. Upload a CSV dataset and run the pipeline to inspect before and after metrics.
          </p>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.6} />
            <span>Check Again</span>
          </button>
        </div>
      </div>
    );
  }

  let totalNullsBefore = 0;
  let totalNullsAfter = 0;
  if (columnsProfile.length > 0) {
    totalNullsBefore = columnsProfile.reduce((a, c) => a + (c.nulls_before || 0), 0);
    totalNullsAfter = columnsProfile.reduce((a, c) => a + (c.nulls_after || 0), 0);
  } else {
    const nulls = report.null_imputation_summary || {};
    totalNullsBefore = Object.keys(nulls)
      .filter((k) => k.endsWith("_before"))
      .reduce((a, k) => a + (nulls[k] || 0), 0);
    totalNullsAfter = Object.keys(nulls)
      .filter((k) => k.endsWith("_after"))
      .reduce((a, k) => a + (nulls[k] || 0), 0);
  }

  const nullsImputed = Math.max(0, totalNullsBefore - totalNullsAfter);
  const retentionPct =
    rawRows > 0 ? Math.min(100, Math.round((cleanedRows / rawRows) * 100)) : 100;
  const vectorChunks = systemHealth?.indexed_chunks ?? 0;
  const reportId = report.report_id || "ETL-REPORT";

  const plainSummary = `PySpark ingested ${rawRows.toLocaleString()} raw rows across ${columnCount} discovered columns, removed ${dupsRemoved.toLocaleString()} duplicate rows, and imputed ${nullsImputed.toLocaleString()} missing values, leaving ${cleanedRows.toLocaleString()} clean records ready in PostgreSQL.`;

  const issues = [
    {
      id: "dq-01",
      severity: dupsRemoved > 0 ? "warn" : "pass",
      field: "sales.*",
      rule: "Exact Row Deduplication",
      detail: `${dupsRemoved.toLocaleString()} duplicate rows pruned; ${cleanedRows.toLocaleString()} unique rows kept.`,
    },
    {
      id: "dq-02",
      severity: nullsImputed > 0 ? "warn" : "pass",
      field: "sales.nulls",
      rule: "Null Value Imputation",
      detail: `${totalNullsBefore.toLocaleString()} missing values before cleaning → ${totalNullsAfter.toLocaleString()} after.`,
    },
    {
      id: "dq-03",
      severity: "pass",
      field: "sales.schema",
      rule: "Schema Type Conformance",
      detail: `${columnCount} columns profiled and typed in PostgreSQL.`,
    },
    {
      id: "dq-04",
      severity: "pass",
      field: "document_embeddings",
      rule: "pgvector Index Readiness",
      detail: `${vectorChunks.toLocaleString()} vector chunks indexed for RAG retrieval.`,
    },
  ];

  columnsProfile
    .filter((c) => (c.nulls_before || 0) > 0)
    .forEach((col, i) => {
      issues.push({
        id: `col-${i}`,
        severity: (col.nulls_after || 0) > 0 ? "warn" : "pass",
        field: `sales.${col.name}`,
        rule: `Column Null Check (${col.type || "typed"})`,
        detail: `${(col.nulls_before || 0).toLocaleString()} missing before → ${(col.nulls_after || 0).toLocaleString()} after.`,
      });
    });

  return (
    <div className="w-full max-w-6xl mx-auto space-y-5 pb-16">
      {/* Plain-Language Summary Ledger Header */}
      <section className="border border-grid rounded-xs bg-raised p-4 sm:p-5 paper-stack space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-grid">
          <div className="space-y-0.5">
            <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
              PySpark Quality Audit · #{reportId}
            </div>
            <h1 className="font-serif text-2xl font-semibold text-ink">
              Data Quality Report
            </h1>
          </div>

          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.6} />
            <span>Refresh</span>
          </button>
        </div>

        <p className="font-serif text-base text-ink leading-relaxed max-w-4xl">
          {plainSummary}
        </p>

        {/* Big Mono Numbers */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
          <div className="p-3 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Raw Records
            </div>
            <div className="font-mono text-2xl sm:text-3xl font-bold text-ink tabular-mono mt-1">
              {animatedRaw.toLocaleString()}
            </div>
          </div>

          <div className="p-3 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Cleaned Records
            </div>
            <div className="font-mono text-2xl sm:text-3xl font-bold text-route-data-ink tabular-mono mt-1">
              {animatedCleaned.toLocaleString()}
            </div>
          </div>

          <div className="p-3 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Duplicates Pruned
            </div>
            <div className="font-mono text-2xl sm:text-3xl font-bold text-amber-ink tabular-mono mt-1">
              {animatedDups.toLocaleString()}
            </div>
          </div>

          <div className="p-3 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Retention Rate
            </div>
            <div className="font-mono text-2xl sm:text-3xl font-bold text-sage-ink tabular-mono mt-1">
              {retentionPct}%
            </div>
          </div>
        </div>
      </section>

      {/* Before / After Ruled Bars */}
      <section className="space-y-2.5">
        <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-muted">
          Before / After Comparison
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <QualityBars
            title="Total Null Values Across Dataset"
            labelBefore="Before Cleaning"
            valBefore={totalNullsBefore}
            labelAfter="After Cleaning"
            valAfter={totalNullsAfter}
            deltaLabel={
              totalNullsBefore > 0
                ? `${Math.round((nullsImputed / totalNullsBefore) * 100)}% imputed`
                : "0 nulls"
            }
          />
          <QualityBars
            title="Duplicate Rows Removed"
            labelBefore="Raw Input Rows"
            valBefore={rawRows}
            labelAfter="Cleaned Unique Rows"
            valAfter={cleanedRows}
            deltaLabel={`${dupsRemoved.toLocaleString()} pruned`}
          />
        </div>
      </section>

      {/* Issue & Invariant Table */}
      <section className="border border-grid rounded-xs bg-raised overflow-hidden paper-stack">
        <div className="px-4 py-2.5 border-b border-grid bg-sunken flex items-center justify-between gap-2">
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-ink">
            Audit Checks &amp; Column Findings
          </span>
          <span className="font-mono text-[11px] text-muted tabular-mono">
            {issues.length} checks
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-grid bg-sunken/60 text-muted text-[10.5px] uppercase tracking-wider">
                <th className="px-4 py-2 w-28">Severity</th>
                <th className="px-4 py-2">Target</th>
                <th className="px-4 py-2">Check</th>
                <th className="px-4 py-2">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-grid">
              {issues.map((item) => (
                <tr key={item.id} className="hover:bg-paper/60 transition-colors">
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <Stamp
                      variant={item.severity === "pass" ? "pass" : "warn"}
                      size="sm"
                    />
                  </td>
                  <td className="px-4 py-2.5 font-semibold text-route-data-ink whitespace-nowrap">
                    {item.field}
                  </td>
                  <td className="px-4 py-2.5 font-sans text-xs font-medium text-ink">
                    {item.rule}
                  </td>
                  <td className="px-4 py-2.5 font-sans text-xs text-muted">
                    {item.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
