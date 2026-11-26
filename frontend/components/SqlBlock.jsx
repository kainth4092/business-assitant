"use client";

import React, { useState } from "react";
import { Copy, Check, Terminal } from "lucide-react";

const SQL_KEYWORDS = new Set([
  "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "LIMIT",
  "AND", "OR", "IN", "AS", "DESC", "ASC", "JOIN", "ON", "LEFT",
  "RIGHT", "INNER", "OUTER", "IS", "NOT", "NULL", "SET", "UPDATE",
  "SUM", "AVG", "ROUND", "COUNT", "MIN", "MAX", "DISTINCT",
  "NUMERIC", "HAVING", "CASE", "WHEN", "THEN", "ELSE", "END", "TRIM", "UPPER"
]);

export default function SqlBlock({ sql, executionTime = null, label = "PostgreSQL · Read-Only" }) {
  const [copied, setCopied] = useState(false);

  if (!sql) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const tokens = sql.split(/(\s+|,|\(|\))/);

  return (
    <div
      className="border rounded-xs overflow-hidden font-mono text-xs"
      style={{
        backgroundColor: "var(--sql-bg)",
        color: "var(--sql-fg)",
        borderColor: "var(--sql-border)",
      }}
    >
      <div
        className="flex items-center justify-between gap-2 px-3 py-1.5 border-b text-[11px]"
        style={{ borderColor: "var(--sql-border)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Terminal className="w-3.5 h-3.5 shrink-0" style={{ color: "var(--sql-kw)" }} strokeWidth={1.5} />
          <span className="uppercase tracking-wider font-semibold truncate" style={{ color: "var(--sql-fg)" }}>
            {label}
          </span>
          {executionTime && (
            <span className="text-[10px] opacity-75 shrink-0 tabular-mono">
              {executionTime}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs border text-[10px] font-semibold transition-opacity hover:opacity-85 cursor-pointer shrink-0"
          style={{
            borderColor: "var(--sql-border)",
            color: "var(--sql-fg)",
          }}
          aria-label="Copy SQL query"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3" style={{ color: "var(--sage)" }} strokeWidth={1.8} />
              <span>Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" strokeWidth={1.6} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      <pre className="p-3 overflow-x-auto leading-relaxed whitespace-pre-wrap break-words text-[12px] m-0">
        {tokens.map((token, idx) => {
          const upper = token.toUpperCase();
          if (SQL_KEYWORDS.has(upper)) {
            return (
              <span key={idx} style={{ color: "var(--sql-kw)", fontWeight: 700 }}>
                {token}
              </span>
            );
          }
          if (/^\d+(\.\d+)?$/.test(token)) {
            return (
              <span key={idx} style={{ color: "var(--sql-num)", fontWeight: 600 }}>
                {token}
              </span>
            );
          }
          return <span key={idx}>{token}</span>;
        })}
      </pre>
    </div>
  );
}
