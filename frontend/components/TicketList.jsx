"use client";

import React from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  FileCode,
  HelpCircle,
  MessageSquare,
  ShieldAlert,
  XCircle,
  Plus
} from "lucide-react";

export default function TicketList({
  tickets = [],
  selectedTicketId = null,
  onSelectTicket = () => {},
  filterStatus = "all",
  onChangeFilter = () => {},
  onOpenNewTicketModal = () => {}
}) {
  const filteredTickets = tickets.filter((t) => {
    if (filterStatus === "all") return true;
    if (filterStatus === "fix_ready") return t.status === "fix_ready";
    if (filterStatus === "code_bug") return t.classification === "code_bug";
    if (filterStatus === "data_issue") return t.classification === "data_issue";
    if (filterStatus === "done") return t.status === "done";
    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case "fix_ready":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent-lime/15 text-primary border border-accent-lime/40 font-mono text-[10px] font-bold shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-lime animate-pulse" />
            APPROVAL
          </span>
        );
      case "done":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30 font-mono text-[10px] font-bold shrink-0">
            <CheckCircle2 className="w-3 h-3 stroke-[2.2]" />
            APPLIED
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent-crimson/15 text-accent-crimson border border-accent-crimson/30 font-mono text-[10px] font-bold shrink-0">
            <XCircle className="w-3 h-3 stroke-[2.2]" />
            REJECTED
          </span>
        );
      case "investigating":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30 font-mono text-[10px] font-bold shrink-0">
            <Clock className="w-3 h-3 stroke-[2.2]" />
            TRIAGE
          </span>
        );
    }
  };

  const getClassificationBadge = (classification) => {
    switch (classification) {
      case "code_bug":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-crimson/10 text-accent-crimson font-mono text-[10px] font-bold border border-accent-crimson/30">
            <FileCode className="w-3 h-3 stroke-[2]" />
            BUG
          </span>
        );
      case "data_issue":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-cyan/10 text-accent-cyan font-mono text-[10px] font-bold border border-accent-cyan/30">
            <Database className="w-3 h-3 stroke-[2]" />
            DATA
          </span>
        );
      case "question":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-amber/10 text-accent-amber font-mono text-[10px] font-bold border border-accent-amber/30">
            <HelpCircle className="w-3 h-3 stroke-[2]" />
            DOCS
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-container text-muted font-mono text-[10px] font-bold border border-border">
            TASK
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface-lowest">
      {/* Header & Filter Bay */}
      <div className="p-3.5 border-b border-border space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
              Support Backlog
            </span>
            <span className="px-1.5 py-0.5 rounded bg-surface-container font-mono text-[10px] text-primary font-bold">
              {filteredTickets.length}
            </span>
          </div>

          <button
            onClick={onOpenNewTicketModal}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-accent-lime text-accent-lime-contrast font-headline text-[11px] font-bold hover:bg-accent-lime/90 active:scale-95 transition-all shadow-xs"
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
            <span>Simulate Client</span>
          </button>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-0.5 text-xs no-scrollbar">
          {[
            { id: "all", label: "All" },
            { id: "fix_ready", label: "HITL Gated" },
            { id: "code_bug", label: "Bugs" },
            { id: "data_issue", label: "Data" },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => onChangeFilter(f.id)}
              className={`px-2.5 py-1 rounded text-xs font-mono font-bold whitespace-nowrap transition-colors ${
                filterStatus === f.id
                  ? "bg-surface-container-high text-primary border border-border shadow-xs"
                  : "text-muted hover:text-primary hover:bg-surface-container"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Ticket List Cards */}
      <div className="flex-1 overflow-y-auto divide-y divide-border">
        {filteredTickets.length === 0 ? (
          <div className="p-8 text-center text-muted font-sans text-xs space-y-2">
            <MessageSquare className="w-6 h-6 stroke-[1.5] mx-auto text-muted mb-2 opacity-60" />
            <div className="font-bold text-primary">No Tickets Found</div>
            <p className="text-muted leading-relaxed">
              No tickets match the selected filter. Click &ldquo;Simulate Client&rdquo; above to inject a ticket.
            </p>
          </div>
        ) : (
          filteredTickets.map((ticket) => {
            const isSelected = selectedTicketId === ticket.id;
            const titleText = ticket.title || ticket.issue || ticket.message || "Client Inquiry";
            const clientName = ticket.client_name || ticket.sender_name || ticket.sender || "Client";
            
            return (
              <button
                key={ticket.id}
                type="button"
                onClick={() => onSelectTicket(ticket.id)}
                className={`w-full text-left p-3.5 transition-all flex flex-col gap-2 relative ${
                  isSelected
                    ? "bg-surface-container-high border-l-4 border-l-accent-lime"
                    : "bg-surface-lowest hover:bg-surface-low border-l-4 border-l-transparent"
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="font-mono text-[11px] font-bold text-muted truncate">
                      #{ticket.id}
                    </span>
                    {getClassificationBadge(ticket.classification)}
                  </div>
                  {getStatusBadge(ticket.status)}
                </div>

                <div className="font-headline text-body-md font-bold text-primary line-clamp-2 leading-snug">
                  {titleText}
                </div>

                <div className="flex items-center justify-between text-muted font-mono text-[10px]">
                  <span className="truncate max-w-[150px]">
                    {clientName} &middot; {ticket.channel || "slack"}
                  </span>
                  <span>{ticket.timestamp || ticket.created_at?.slice(11, 16) || "Just now"}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
