"use client";

import React from "react";
import { Plus, Search } from "lucide-react";
import Strip from "./Strip";
import Skeleton from "./Skeleton";

const BOARD_COLUMNS = [
  { id: "new", label: "New", match: (t) => t.status === "new" },
  { id: "investigating", label: "Investigating", match: (t) => t.status === "investigating" },
  { id: "fix_ready", label: "Fix ready", match: (t) => t.status === "fix_ready" && !t.is_flagged },
  { id: "applied", label: "Applied", match: (t) => t.status === "done" || t.status === "approved" },
  {
    id: "rejected",
    label: "Rejected",
    match: (t) => t.status === "rejected" || t.status === "flagged" || Boolean(t.is_flagged),
  },
];

export default function StripBoard({
  tickets = [],
  selectedTicketId = null,
  newTicketIds = [],
  filterCategory = "all",
  onChangeCategory = () => {},
  searchQuery = "",
  onSearchChange = () => {},
  onSelectTicket = () => {},
  onOpenNewTicketModal = () => {},
  isLoading = false,
}) {
  const filtered = tickets.filter((t) => {
    const catOk =
      filterCategory === "all" ||
      (filterCategory === "fix_ready" && t.status === "fix_ready") ||
      t.classification === filterCategory;
    if (!catOk) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(t.id || "").toLowerCase().includes(q) ||
      String(t.message || "").toLowerCase().includes(q) ||
      String(t.client_name || "").toLowerCase().includes(q) ||
      String(t.channel || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-3 board-container">
      {/* Flight Strip Board Controls */}
      <div className="p-3 border border-grid rounded-xs bg-raised flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted mr-1">
            Filter
          </span>
          {[
            { id: "all", label: "All" },
            { id: "fix_ready", label: "Needs Review" },
            { id: "code_bug", label: "Bugs" },
            { id: "data_issue", label: "Data" },
            { id: "question", label: "Docs" },
          ].map((f) => {
            const active = filterCategory === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => onChangeCategory(f.id)}
                className={`px-2 py-1 rounded-xs border font-mono text-[11px] font-semibold cursor-pointer transition-colors ${
                  active
                    ? "border-ink bg-highlighter text-highlighter-ink font-bold"
                    : "border-grid bg-paper text-muted hover:text-ink"
                }`}
              >
                {f.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xs border border-grid bg-paper flex-1 sm:w-52">
            <Search className="w-3.5 h-3.5 text-muted shrink-0" strokeWidth={1.5} />
            <label htmlFor="strip-search" className="sr-only">
              Filter flight strips
            </label>
            <input
              id="strip-search"
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Find ID, sender, issue..."
              className="w-full bg-transparent text-xs text-ink placeholder:text-muted focus:outline-none font-mono"
            />
          </div>

          <button
            type="button"
            onClick={onOpenNewTicketModal}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 cursor-pointer shrink-0"
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span>Simulate Client</span>
          </button>
        </div>
      </div>

      {/* Loading Skeleton */}
      {isLoading && tickets.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
          {BOARD_COLUMNS.map((col) => (
            <div key={col.id} className="border border-grid rounded-xs bg-sunken/50 p-2.5 space-y-2">
              <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-muted pb-1.5 border-b border-grid">
                {col.label}
              </div>
              <Skeleton variant="strips" count={2} />
            </div>
          ))}
        </div>
      ) : tickets.length === 0 ? (
        <div className="border border-grid rounded-xs bg-raised p-8 text-center space-y-2 paper-stack">
          <div className="font-serif text-lg font-semibold text-ink">
            No tickets yet.
          </div>
          <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
            No tickets yet. Send a message from a channel or use Simulate Client.
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={onOpenNewTicketModal}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" strokeWidth={1.8} />
              <span>Simulate Client</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3 items-start">
          {BOARD_COLUMNS.map((col) => {
            const colTickets = filtered.filter(col.match);
            return (
              <section
                key={col.id}
                aria-label={`${col.label} column`}
                className="border border-grid rounded-xs bg-sunken/45 flex flex-col min-w-0"
              >
                <header className="px-3 py-2 border-b border-grid bg-sunken flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink truncate">
                    {col.label}
                  </span>
                  <span className="px-1.5 py-0.2 rounded-xs border border-grid bg-raised font-mono text-[10px] font-bold text-ink tabular-mono">
                    {colTickets.length}
                  </span>
                </header>

                <div className="p-2 space-y-2 min-h-[120px]">
                  {colTickets.length === 0 ? (
                    <div className="py-6 px-2 text-center font-mono text-[10.5px] text-muted">
                      Empty bay
                    </div>
                  ) : (
                    colTickets.map((t) => (
                      <Strip
                        key={t.id}
                        ticket={t}
                        isSelected={selectedTicketId === t.id}
                        isNew={newTicketIds.includes(t.id)}
                        onSelect={onSelectTicket}
                      />
                    ))
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
