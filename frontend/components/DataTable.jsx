"use client";

import React from "react";
import { Table2 } from "lucide-react";

export default function DataTable({ rows = [], maxRows = 10, title = null }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="p-3 rounded-xs border border-grid bg-sunken text-center text-xs text-muted font-mono">
        No rows returned.
      </div>
    );
  }

  const columns = Object.keys(rows[0]);
  const displayedRows = rows.slice(0, maxRows);

  return (
    <div className="border border-grid rounded-xs overflow-hidden bg-raised">
      {title && (
        <div className="px-3 py-1.5 border-b border-grid bg-sunken flex items-center justify-between gap-2 text-[11px] font-mono">
          <div className="flex items-center gap-1.5 min-w-0">
            <Table2 className="w-3.5 h-3.5 text-route-data-ink shrink-0" strokeWidth={1.5} />
            <span className="font-bold text-ink uppercase tracking-wider truncate">
              {title}
            </span>
          </div>
          <span className="text-muted shrink-0 tabular-mono">
            {displayedRows.length}/{rows.length} rows
          </span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse font-mono text-xs">
          <thead>
            <tr className="border-b border-grid bg-sunken text-muted">
              {columns.map((col) => {
                const sampleVal = rows.find((r) => r[col] !== null && r[col] !== undefined)?.[col];
                const isNumCol = typeof sampleVal === "number";
                return (
                  <th
                    key={col}
                    className={`px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider whitespace-nowrap ${
                      isNumCol ? "text-right" : "text-left"
                    }`}
                  >
                    {col.replace(/_/g, " ")}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-grid">
            {displayedRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-sunken/60 transition-colors">
                {columns.map((col) => {
                  const val = row[col];
                  const isNumeric = typeof val === "number";
                  return (
                    <td
                      key={col}
                      className={`px-2.5 py-1.5 text-[11.5px] text-ink tabular-mono max-w-[200px] truncate ${
                        isNumeric ? "text-right font-medium" : "text-left"
                      }`}
                      title={val !== null && val !== undefined ? String(val) : "NULL"}
                    >
                      {isNumeric ? val.toLocaleString() : val === null || val === undefined ? "NULL" : String(val)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > maxRows && (
        <div className="px-3 py-1 bg-sunken border-t border-grid text-right text-[10px] text-muted font-mono tabular-mono">
          +{rows.length - maxRows} additional rows
        </div>
      )}
    </div>
  );
}
