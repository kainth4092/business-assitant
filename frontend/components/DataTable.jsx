"use client";

import React from "react";
import { Table as TableIcon } from "lucide-react";

export default function DataTable({ rows = [], maxRows = 10, title = null }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-surface border border-border text-center text-xs text-muted font-mono">
        No tabular records returned.
      </div>
    );
  }

  const columns = Object.keys(rows[0]);
  const displayedRows = rows.slice(0, maxRows);

  return (
    <div className="border border-border rounded-lg overflow-hidden bg-surface shadow-xs">
      {title && (
        <div className="px-3.5 py-2 border-b border-border bg-surface-low flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <TableIcon className="w-3.5 h-3.5 text-accent-cyan stroke-[2]" />
            <span className="font-bold text-primary uppercase tracking-wider text-[11px]">
              {title}
            </span>
          </div>
          <span className="text-[10px] text-muted font-medium">
            Showing {displayedRows.length} of {rows.length} rows
          </span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse font-mono text-xs">
          <thead>
            <tr className="border-b border-border bg-surface-low text-muted font-bold">
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-[10.5px] uppercase tracking-wider whitespace-nowrap"
                >
                  {col.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {displayedRows.map((row, rIdx) => (
              <tr
                key={rIdx}
                className="hover:bg-surface-low transition-colors"
              >
                {columns.map((col) => {
                  const val = row[col];
                  const numeric = typeof val === "number";
                  return (
                    <td
                      key={col}
                      className={`px-3 py-2 text-[11.5px] text-primary whitespace-nowrap tabular-nums ${
                        numeric ? "text-right font-medium" : "text-left"
                      }`}
                    >
                      {numeric ? val.toLocaleString() : String(val ?? "NULL")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > maxRows && (
        <div className="px-3 py-1.5 bg-surface-low border-t border-border text-right text-[10px] text-muted font-mono">
          + {rows.length - maxRows} additional rows truncated for display
        </div>
      )}
    </div>
  );
}
