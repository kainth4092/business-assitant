"use client";

import React from "react";
import { Radio, Check, AlertTriangle, Slash, Pause } from "lucide-react";
import { getChannelInfo } from "./Strip";
import { formatClockTime } from "../lib/formatters";

function ChannelStateBadge({ status }) {
  switch (status) {
    case "connected":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border border-sage bg-sage-tint text-sage-ink font-mono text-[10px] font-bold uppercase">
          <Check className="w-3 h-3" strokeWidth={1.8} />
          Connected
        </span>
      );
    case "error":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border border-seal bg-seal-tint text-seal-ink font-mono text-[10px] font-bold uppercase">
          <AlertTriangle className="w-3 h-3" strokeWidth={1.8} />
          Error
        </span>
      );
    case "paused":
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border border-amber bg-amber-tint text-amber-ink font-mono text-[10px] font-bold uppercase">
          <Pause className="w-3 h-3" strokeWidth={1.8} />
          Paused
        </span>
      );
    case "not_configured":
    default:
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border border-grid bg-sunken text-muted font-mono text-[10px] font-bold uppercase">
          <Slash className="w-3 h-3" strokeWidth={1.6} />
          Not configured
        </span>
      );
  }
}

export default function ChannelStatus({
  channels = [],
  togglingChannelId = null,
  onToggleChannel = () => {},
}) {
  return (
    <section
      aria-label="Communication channels"
      className="border border-grid rounded-xs bg-raised p-3.5 space-y-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-grid">
        <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-ink">
          <Radio className="w-3.5 h-3.5 text-route-data-ink" strokeWidth={1.6} />
          <span>Communication Channels</span>
        </div>
        <span className="font-mono text-[10.5px] text-muted">
          Allowlisted senders · Env credentials
        </span>
      </div>

      {channels.length === 0 ? (
        <div className="py-3 font-mono text-xs text-muted">
          No channel telemetry loaded yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {channels.map((ch) => {
            const { Icon } = getChannelInfo(ch.id);
            const isToggling = togglingChannelId === ch.id;
            const isTeamsStub = ch.id === "teams";

            return (
              <div
                key={ch.id}
                className="p-3 rounded-xs border border-grid bg-paper/70 flex flex-col justify-between gap-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-7 h-7 rounded-xs border border-grid bg-raised flex items-center justify-center shrink-0">
                      <Icon className="w-3.5 h-3.5 text-ink" strokeWidth={1.6} />
                    </div>
                    <div className="min-w-0">
                      <div className="font-sans text-xs font-bold text-ink truncate">
                        {ch.name}
                      </div>
                      <div className="font-mono text-[10px] text-muted truncate">
                        {ch.mode}
                      </div>
                    </div>
                  </div>

                  {/* Rectangular 2px switch */}
                  <button
                    type="button"
                    role="switch"
                    aria-checked={Boolean(ch.enabled)}
                    aria-label={`Toggle ${ch.name} channel`}
                    disabled={isToggling || isTeamsStub}
                    onClick={() => onToggleChannel(ch.id, !ch.enabled)}
                    title={
                      isTeamsStub
                        ? "Microsoft Teams requires Azure Bot setup (see docs/TEAMS_SETUP.md)"
                        : ch.enabled
                        ? `Pause ${ch.name}`
                        : `Enable ${ch.name}`
                    }
                    className={`relative inline-flex items-center h-5 w-9 rounded-xs border transition-colors shrink-0 ${
                      isTeamsStub
                        ? "bg-sunken border-grid opacity-50 cursor-not-allowed"
                        : ch.enabled
                        ? "bg-sage border-sage cursor-pointer"
                        : "bg-sunken border-grid cursor-pointer"
                    }`}
                  >
                    <span
                      className={`inline-block w-3.5 h-3.5 rounded-xs bg-raised border border-ink/30 transition-transform ${
                        ch.enabled && !isTeamsStub ? "translate-x-4" : "translate-x-0.5"
                      }`}
                    />
                  </button>
                </div>

                <div className="pt-2 border-t border-grid/70 flex items-center justify-between gap-2">
                  <ChannelStateBadge status={ch.status} />
                  <span className="font-mono text-[10px] text-muted tabular-mono truncate">
                    {ch.last_message_at ? formatClockTime(ch.last_message_at) : "No messages yet"}
                  </span>
                </div>

                {ch.error_reason && (
                  <div className="px-2 py-1 rounded-xs border border-seal/40 bg-seal-tint font-mono text-[10px] text-seal-ink leading-snug break-words">
                    {ch.error_reason}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
