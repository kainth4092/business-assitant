"use client";

import React from "react";
import { Mail, Hash, Globe, Terminal, Users } from "lucide-react";
import { formatRelativeAge } from "../lib/formatters";
import Stamp from "./Stamp";

const CHANNEL_MAP = {
  email: { label: "Email", Icon: Mail },
  slack: { label: "Slack", Icon: Hash },
  teams: { label: "Teams", Icon: Users },
  msteams: { label: "Teams", Icon: Users },
  webhook: { label: "Webhook", Icon: Globe },
  simulated: { label: "Simulated", Icon: Terminal },
};

const CATEGORY_MAP = {
  code_bug: { label: "BUG", colorVar: "var(--seal-red-ink)", borderVar: "var(--seal-red)" },
  data_issue: { label: "DATA", colorVar: "var(--route-data-ink)", borderVar: "var(--route-data)" },
  question: { label: "DOCS", colorVar: "var(--route-docs-ink)", borderVar: "var(--route-docs)" },
  security_flagged: { label: "SEC", colorVar: "var(--seal-red-ink)", borderVar: "var(--seal-red)" },
  feature_request: { label: "REQ", colorVar: "var(--muted)", borderVar: "var(--grid-strong)" },
};

export function getChannelInfo(channel) {
  const key = (channel || "webhook").toLowerCase().trim();
  return CHANNEL_MAP[key] || CHANNEL_MAP.webhook;
}

export default function Strip({
  ticket,
  isSelected = false,
  isNew = false,
  onSelect = () => {},
}) {
  const ch = getChannelInfo(ticket.channel);
  const ChannelIcon = ch.Icon;
  const cat = CATEGORY_MAP[ticket.classification] || CATEGORY_MAP.feature_request;

  const stampVariant = ticket.is_flagged || ticket.status === "flagged"
    ? "flagged"
    : ticket.status === "done" || ticket.status === "approved"
    ? "applied"
    : ticket.status === "fix_ready"
    ? "needs_review"
    : ticket.status === "rejected"
    ? "rejected"
    : ticket.status === "investigating"
    ? "investigating"
    : "new";

  const sender = ticket.client_name || ticket.sender_name || ticket.sender || "Operator";
  const summary = ticket.title || ticket.issue || ticket.message || "Support ticket";
  const age = formatRelativeAge(ticket.created_at || ticket.updated_at);

  return (
    <button
      type="button"
      onClick={() => onSelect(ticket.id)}
      data-testid={`ticket-strip-${ticket.id}`}
      className={`strip-card w-full text-left border rounded-xs p-2.5 transition-[transform,border-color,background-color] duration-150 hover:-translate-y-px cursor-pointer flex flex-col gap-2 ${
        isNew ? "animate-strip-in" : ""
      } ${
        isSelected
          ? "border-ink bg-highlighter-wash paper-stack-strong"
          : "border-grid bg-raised hover:border-grid-strong paper-stack"
      }`}
      style={{
        borderInlineStartWidth: "3px",
        borderInlineStartColor: cat.borderVar,
      }}
    >
      {/* Fixed Field Row 1: Callsign ID · Category · State Stamp */}
      <div className="flex items-center justify-between gap-1.5 min-w-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-mono text-[10.5px] font-bold text-ink tabular-mono truncate">
            #{ticket.id}
          </span>
          <span
            className="px-1 py-0 rounded-xs border font-mono text-[9.5px] font-bold uppercase tracking-wider shrink-0"
            style={{
              color: cat.colorVar,
              borderColor: cat.borderVar,
            }}
          >
            {cat.label}
          </span>
        </div>

        <Stamp variant={stampVariant} size="sm" />
      </div>

      {/* Summary Line (clamped safely for long messages) */}
      <div className="font-sans text-xs font-medium text-ink leading-snug line-clamp-2 break-words">
        {summary}
      </div>

      {/* Fixed Field Row 2: Channel · Sender · Age */}
      <div className="pt-1.5 border-t border-grid/70 flex items-center justify-between gap-2 min-w-0">
        <div
          className={`flex items-center gap-1.5 min-w-0 font-mono text-[10px] ${
            isSelected ? "text-ink" : "text-muted"
          }`}
        >
          <ChannelIcon className="w-3 h-3 shrink-0 text-ink" strokeWidth={1.6} />
          <span className="shrink-0">{ch.label}</span>
          <span aria-hidden="true">·</span>
          <span className="truncate text-ink/90" title={sender}>
            {sender}
          </span>
        </div>

        <span
          className={`font-mono text-[10px] tabular-mono shrink-0 ${
            isSelected ? "text-ink font-semibold" : "text-muted"
          }`}
        >
          {age}
        </span>
      </div>
    </button>
  );
}
