"use client";

import React, { useState } from "react";
import { Copy, Check, Terminal } from "lucide-react";

const SQL_KEYWORDS = new Set([
  "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "LIMIT",
  "AND", "OR", "IN", "AS", "DESC", "ASC", "JOIN", "ON",
  "SUM", "AVG", "ROUND", "COUNT", "MIN", "MAX", "DISTINCT", "NUMERIC", "HAVING", "CASE", "WHEN", "THEN", "ELSE", "END"
]);

export default function SqlBlock({ sql, executionTime = null }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!sql) return;
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!sql) return null;

  const tokens = sql.split(/(\s+|,|\(|\))/);

  return (
    <div className="relative border border-border rounded-lg overflow-hidden text-xs font-mono bg-[#0E1116] text-[#F0F6FC] shadow-xs">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#2A323C] bg-[#161B22] text-[11px]">
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-accent-cyan stroke-[2]" />
          <span className="uppercase tracking-wider font-bold text-[#8B949E]">
            PostgreSQL &middot; Read-Only Query
          </span>
          {executionTime && (
            <span className="text-[#8B949E] text-[10px]">
              ({executionTime})
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[#C9D1D9] hover:text-white transition-all px-2 py-0.5 rounded bg-[#1D242D] hover:bg-[#272A30] border border-[#2A323C]"
          title="Copy SQL to clipboard"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-accent-emerald stroke-[2.2]" />
              <span className="text-[10px] text-accent-emerald font-bold">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3 stroke-[1.8]" />
              <span className="text-[10px] font-medium">Copy SQL</span>
            </>
          )}
        </button>
      </div>

      <div className="p-3 overflow-x-auto leading-relaxed whitespace-pre-wrap break-all text-[12px] font-mono">
        {tokens.map((token, i) => {
          const upper = token.toUpperCase();
          if (SQL_KEYWORDS.has(upper)) {
            return (
              <span key={i} className="text-[#22D3EE] font-bold">
                {token}
              </span>
            );
          }
          if (/^\d+(\.\d+)?$/.test(token)) {
            return (
              <span key={i} className="text-[#F59E0B] font-semibold">
                {token}
              </span>
            );
          }
          return (
            <span key={i} className="text-[#F0F6FC]">
              {token}
            </span>
          );
        })}
      </div>
    </div>
  );
}
