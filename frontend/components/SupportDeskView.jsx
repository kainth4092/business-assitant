"use client";

import React, { useState, useEffect, useRef } from "react";
import { RefreshCw, Send, X } from "lucide-react";
import StripBoard from "./StripBoard";
import TicketDetail from "./TicketDetail";
import ChannelStatus from "./ChannelStatus";
import ErrorState from "./ErrorState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SupportDeskView({
  onUpdatePendingCount = () => {},
  externalTicketId = null,
  onClearExternalTicket = () => {},
}) {
  const [tickets, setTickets] = useState([]);
  const [channels, setChannels] = useState([]);
  const [togglingChannelId, setTogglingChannelId] = useState(null);
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  const [isLoadingTickets, setIsLoadingTickets] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [stampAnimate, setStampAnimate] = useState(false);
  const [newTicketIds, setNewTicketIds] = useState([]);

  const [filterCategory, setFilterCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [notificationBanner, setNotificationBanner] = useState(null);

  // Simulate Client modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [customSender, setCustomSender] = useState("Client Operator");
  const [customEmail, setCustomEmail] = useState("client@company.com");
  const [customChannel, setCustomChannel] = useState("simulated");
  const [customMessage, setCustomMessage] = useState("");

  const knownIdsRef = useRef(new Set());

  const fetchChannels = async () => {
    try {
      const res = await fetch(`${API_BASE}/support/channels`);
      if (res.ok) {
        const data = await res.json();
        setChannels(data.channels || []);
      }
    } catch {
      // Channels remain empty if backend is down
    }
  };

  const fetchTickets = async (silent = false) => {
    if (!silent) setIsLoadingTickets(true);
    setLoadError(null);
    try {
      const res = await fetch(`${API_BASE}/support/tickets`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status} while loading tickets`);
      }
      const data = await res.json();
      const list = data.tickets || [];

      if (knownIdsRef.current.size > 0) {
        const arrived = list
          .filter((t) => !knownIdsRef.current.has(t.id))
          .map((t) => t.id);
        if (arrived.length > 0) {
          setNewTicketIds(arrived);
          setTimeout(() => setNewTicketIds([]), 400);
        }
      }
      list.forEach((t) => knownIdsRef.current.add(t.id));

      setTickets(list);
      onUpdatePendingCount(
        list.filter((t) => t.status === "fix_ready" && !t.is_flagged).length
      );
    } catch (e) {
      if (!silent) setLoadError(e.message || "Could not load support tickets.");
    } finally {
      setIsLoadingTickets(false);
    }
  };

  const fetchTicketDetail = async (ticketId) => {
    setIsLoadingDetail(true);
    try {
      const res = await fetch(`${API_BASE}/support/tickets/${ticketId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedTicket(data);
      }
    } catch {
      // keep existing state
    } finally {
      setIsLoadingDetail(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/support/tickets`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          const list = data.tickets || [];
          list.forEach((t) => knownIdsRef.current.add(t.id));
          setTickets(list);
          onUpdatePendingCount(
            list.filter((t) => t.status === "fix_ready" && !t.is_flagged).length
          );
        }
      } catch (e) {
        if (!cancelled) setLoadError(e.message || "Could not load support tickets.");
      }
    })();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/support/channels`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          setChannels(data.channels || []);
        }
      } catch {
        // ignore
      }
    })();

    const timer = setInterval(() => {
      fetchTickets(true);
      fetchChannels();
    }, 8000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!externalTicketId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/support/tickets/${externalTicketId}`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          setSelectedTicketId(externalTicketId);
          setSelectedTicket(data);
          setIsSheetOpen(true);
          setStampAnimate(false);
        }
      } finally {
        if (!cancelled) onClearExternalTicket();
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalTicketId]);

  const handleSelectTicket = (ticketId) => {
    setSelectedTicketId(ticketId);
    setStampAnimate(false);
    setIsSheetOpen(true);
    fetchTicketDetail(ticketId);
  };

  const handleToggleChannel = async (channelId, enabled) => {
    setTogglingChannelId(channelId);
    try {
      const res = await fetch(`${API_BASE}/support/channels/${channelId}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (res.ok) {
        const data = await res.json();
        setChannels(data.channels || []);
      }
    } finally {
      setTogglingChannelId(null);
    }
  };

  const handleSendMessage = async (msgPayload) => {
    setIsSubmittingMessage(true);
    setNotificationBanner(null);
    try {
      const res = await fetch(`${API_BASE}/support/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msgPayload),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP ${res.status}`);
      }
      const newTicket = await res.json();
      setIsModalOpen(false);
      setCustomMessage("");
      setNewTicketIds([newTicket.id]);
      setTimeout(() => setNewTicketIds([]), 400);
      await fetchTickets(true);
      setSelectedTicketId(newTicket.id);
      setSelectedTicket(newTicket);
      setIsSheetOpen(true);
      setNotificationBanner({
        type: "success",
        text: `Strip #${newTicket.id} logged and triaged.`,
      });
    } catch (err) {
      setNotificationBanner({
        type: "error",
        text: `Dispatch failed: ${err.message}`,
      });
    } finally {
      setIsSubmittingMessage(false);
    }
  };

  const handleApprove = async (ticketId) => {
    setIsApproving(true);
    setNotificationBanner(null);
    try {
      const res = await fetch(`${API_BASE}/support/tickets/${ticketId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operator_name: "Operations Admin" }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setStampAnimate(true);
      setSelectedTicket(data.ticket);
      setNotificationBanner({
        type: "success",
        text: `Ticket #${ticketId} approved and applied.`,
      });
      await fetchTickets(true);
    } catch (err) {
      setNotificationBanner({
        type: "error",
        text: `Approval failed: ${err.message}`,
      });
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async (ticketId, reason) => {
    setIsRejecting(true);
    setNotificationBanner(null);
    try {
      const res = await fetch(`${API_BASE}/support/tickets/${ticketId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: reason || "Rejected by operator",
          operator_name: "Operations Admin",
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setStampAnimate(true);
      setSelectedTicket(data.ticket);
      setNotificationBanner({
        type: "success",
        text: `Ticket #${ticketId} marked rejected.`,
      });
      await fetchTickets(true);
    } catch (err) {
      setNotificationBanner({
        type: "error",
        text: `Rejection failed: ${err.message}`,
      });
    } finally {
      setIsRejecting(false);
    }
  };

  const pendingCount = tickets.filter(
    (t) => t.status === "fix_ready" && !t.is_flagged
  ).length;
  const appliedCount = tickets.filter(
    (t) => t.status === "done" || t.status === "approved"
  ).length;
  const fixRate =
    tickets.length > 0 ? `${Math.round((appliedCount / tickets.length) * 100)}%` : "—";

  return (
    <div className="w-full max-w-6xl mx-auto space-y-4 pb-16">
      {/* Control Header & Fixed Telemetry Strip */}
      <section className="border border-grid rounded-xs bg-raised p-4 paper-stack space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-grid">
          <div>
            <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
              Flight-Strip Traffic Board
            </div>
            <h1 className="font-serif text-2xl font-semibold text-ink">
              Support Desk &amp; Remediation
            </h1>
          </div>

          <button
            type="button"
            onClick={() => {
              fetchTickets();
              fetchChannels();
            }}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xs border border-grid bg-paper text-ink hover:border-ink font-mono text-xs font-semibold cursor-pointer"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isLoadingTickets ? "animate-spin" : ""}`}
              strokeWidth={1.6}
            />
            <span>Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Active Strips
            </div>
            <div className="font-mono text-xl font-bold text-ink tabular-mono mt-1">
              {tickets.length}
            </div>
          </div>

          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Needs Review
            </div>
            <div className="font-mono text-xl font-bold text-seal-ink tabular-mono mt-1">
              {pendingCount}
            </div>
          </div>

          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Applied Rate
            </div>
            <div className="font-mono text-xl font-bold text-sage-ink tabular-mono mt-1">
              {fixRate}
            </div>
          </div>

          <div className="p-2.5 rounded-xs border border-grid bg-paper">
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
              Sandbox Latency
            </div>
            <div className="font-mono text-xl font-bold text-ink tabular-mono mt-1">
              {selectedTicket?.sandbox_diff?.latency
                ? `${selectedTicket.sandbox_diff.latency}s`
                : "—"}
            </div>
          </div>
        </div>
      </section>

      {loadError && (
        <ErrorState
          title="Support Desk Unavailable"
          message={loadError}
          onRetry={() => fetchTickets()}
        />
      )}

      {notificationBanner && (
        <div
          role="status"
          className={`px-3.5 py-2.5 rounded-xs border flex items-center justify-between gap-2 font-mono text-xs ${
            notificationBanner.type === "success"
              ? "border-sage bg-sage-tint text-sage-ink"
              : "border-seal bg-seal-tint text-seal-ink"
          }`}
        >
          <span>{notificationBanner.text}</span>
          <button
            type="button"
            onClick={() => setNotificationBanner(null)}
            className="underline font-bold cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Flight Strip Board */}
      <StripBoard
        tickets={tickets}
        selectedTicketId={selectedTicketId}
        newTicketIds={newTicketIds}
        filterCategory={filterCategory}
        onChangeCategory={setFilterCategory}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSelectTicket={handleSelectTicket}
        onOpenNewTicketModal={() => setIsModalOpen(true)}
        isLoading={isLoadingTickets}
      />

      {/* Channels Panel */}
      <ChannelStatus
        channels={channels}
        togglingChannelId={togglingChannelId}
        onToggleChannel={handleToggleChannel}
      />

      {/* Ticket Detail Sheet */}
      <TicketDetail
        key={selectedTicket?.id || "empty"}
        ticket={selectedTicket}
        isOpen={isSheetOpen}
        isLoading={isLoadingDetail}
        onClose={() => setIsSheetOpen(false)}
        onApprove={handleApprove}
        onReject={handleReject}
        isApproving={isApproving}
        isRejecting={isRejecting}
        stampAnimate={stampAnimate}
      />

      {/* Simulate Client Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/45"
          role="dialog"
          aria-modal="true"
          aria-label="Simulate client problem report"
          onClick={() => setIsModalOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-xs border border-ink bg-raised paper-stack-strong p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-2.5 border-b border-grid">
              <h2 className="font-serif text-lg font-semibold text-ink">
                Simulate Client Report
              </h2>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded-xs border border-grid text-muted hover:text-ink cursor-pointer"
                aria-label="Close modal"
              >
                <X className="w-4 h-4" strokeWidth={1.6} />
              </button>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label
                    htmlFor="sim-sender"
                    className="block font-mono text-[10px] font-bold uppercase tracking-wider text-muted mb-1"
                  >
                    Sender Name
                  </label>
                  <input
                    id="sim-sender"
                    type="text"
                    value={customSender}
                    onChange={(e) => setCustomSender(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-xs border border-grid bg-paper text-xs text-ink font-sans focus:outline-none"
                  />
                </div>

                <div>
                  <label
                    htmlFor="sim-channel"
                    className="block font-mono text-[10px] font-bold uppercase tracking-wider text-muted mb-1"
                  >
                    Channel
                  </label>
                  <select
                    id="sim-channel"
                    value={customChannel}
                    onChange={(e) => setCustomChannel(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-xs border border-grid bg-paper text-xs text-ink font-mono focus:outline-none"
                  >
                    <option value="simulated">Simulated</option>
                    <option value="slack">Slack</option>
                    <option value="email">Email</option>
                    <option value="webhook">Webhook</option>
                    <option value="teams">Microsoft Teams</option>
                  </select>
                </div>
              </div>

              <div>
                <label
                  htmlFor="sim-email"
                  className="block font-mono text-[10px] font-bold uppercase tracking-wider text-muted mb-1"
                >
                  Sender Email
                </label>
                <input
                  id="sim-email"
                  type="email"
                  value={customEmail}
                  onChange={(e) => setCustomEmail(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-xs border border-grid bg-paper text-xs text-ink font-mono focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="sim-message"
                  className="block font-mono text-[10px] font-bold uppercase tracking-wider text-muted mb-1"
                >
                  Problem Report
                </label>
                <textarea
                  id="sim-message"
                  rows={4}
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  placeholder="Describe a data inconsistency, policy inquiry, or calculation defect..."
                  className="w-full p-2.5 rounded-xs border border-grid bg-paper text-xs text-ink placeholder:text-muted font-sans focus:outline-none"
                />
              </div>

              <button
                type="button"
                disabled={isSubmittingMessage || !customMessage.trim()}
                onClick={() =>
                  handleSendMessage({
                    client_name: customSender,
                    sender: customSender,
                    client_email: customEmail,
                    sender_email: customEmail,
                    channel: customChannel,
                    message: customMessage.trim(),
                  })
                }
                className="w-full py-2 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-40 cursor-pointer inline-flex items-center justify-center gap-2"
              >
                <Send className="w-3.5 h-3.5" strokeWidth={1.6} />
                <span>
                  {isSubmittingMessage ? "Triaging..." : "Dispatch to Support Desk"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
