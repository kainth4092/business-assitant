"use client";

import React, { useState, useEffect } from "react";
import {
  LifeBuoy,
  Send,
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  Terminal,
  FileCode,
  Copy,
  Check,
  RefreshCw,
  RotateCw,
  GitPullRequest,
  Database,
  Layers,
  ArrowRight,
  User,
  MessageSquare,
  Sparkles,
  XCircle,
  HelpCircle,
  Plus,
  X
} from "lucide-react";
import TicketList from "./TicketList";
import TicketDetail from "./TicketDetail";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const PRESET_CLIENT_MESSAGES = [
  {
    type: "data_issue",
    label: "Data Issue: Inconsistent Fat Labels",
    sender: "Alex Chen",
    email: "alex.chen@bigmart-retail.com",
    channel: "slack",
    message: "In the sales reports, LF and Low Fat are showing up as separate categories. Can you merge them?"
  },
  {
    type: "code_bug",
    label: "Code Bug: Inverted Discount Calculation",
    sender: "David Miller",
    email: "david.miller@bigmart-retail.com",
    channel: "teams",
    message: "The discount calculation in demo_target calculates the discounted price as price + discount instead of price - discount! Outlet totals are inflated."
  },
  {
    type: "question",
    label: "Policy Inquiry: Perishable Food Returns",
    sender: "Elena Rostova",
    email: "elena.r@bigmart-retail.com",
    channel: "webhook",
    message: "What is our store policy on customer returns for perishable dairy and meat items?"
  }
];

export default function SupportDeskView({ onUpdatePendingCount = () => {} }) {
  const [tickets, setTickets] = useState([]);
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [isLoadingTickets, setIsLoadingTickets] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  // Filter state: 'all' | 'fix_ready' | 'code_bug' | 'data_issue' | 'done'
  const [filterStatus, setFilterStatus] = useState("all");

  // New Ticket Simulation Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [customSender, setCustomSender] = useState("Client Operations");
  const [customEmail, setCustomEmail] = useState("ops@bigmart-retail.com");
  const [customChannel, setCustomChannel] = useState("slack");
  const [customMessage, setCustomMessage] = useState("");
  const [notificationBanner, setNotificationBanner] = useState(null);

  useEffect(() => {
    fetchTickets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedTicketId) {
      fetchTicketDetail(selectedTicketId);
    }
  }, [selectedTicketId]);

  const fetchTickets = async () => {
    setIsLoadingTickets(true);
    try {
      const res = await fetch(`${API_BASE}/support/tickets`);
      if (res.ok) {
        const data = await res.json();
        const list = data.tickets || [];
        setTickets(list);
        onUpdatePendingCount(list.filter((t) => t.status === "fix_ready").length);
        if (list.length > 0 && !selectedTicketId) {
          setSelectedTicketId(list[0].id);
        }
      }
    } catch (e) {
      console.warn("Could not fetch support tickets:", e);
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
    } catch (e) {
      console.warn(`Could not fetch ticket detail for ${ticketId}:`, e);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleSendMessage = async (msgPayload) => {
    setIsSubmittingMessage(true);
    setNotificationBanner(null);
    try {
      const res = await fetch(`${API_BASE}/support/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msgPayload)
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP Error ${res.status}`);
      }
      const newTicket = await res.json();
      setNotificationBanner({
        type: "success",
        text: `Ticket #${newTicket.id} triaged and investigated by agent.`
      });
      setIsModalOpen(false);
      setCustomMessage("");
      await fetchTickets();
      setSelectedTicketId(newTicket.id);
      setSelectedTicket(newTicket);
    } catch (err) {
      setNotificationBanner({
        type: "error",
        text: `Failed to dispatch message: ${err.message}`
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
        body: JSON.stringify({ operator_name: "Senior Operations Admin" })
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP Error ${res.status}`);
      }
      const data = await res.json();
      setSelectedTicket(data.ticket);
      setNotificationBanner({
        type: "success",
        text: `Remediation for ticket #${ticketId} approved and applied to production!`
      });
      await fetchTickets();
    } catch (err) {
      setNotificationBanner({
        type: "error",
        text: `Approval failed: ${err.message}`
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
          reason: reason || "Rejected by administrator",
          operator_name: "Senior Operations Admin"
        })
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP Error ${res.status}`);
      }
      const data = await res.json();
      setSelectedTicket(data.ticket);
      setNotificationBanner({
        type: "success",
        text: `Ticket #${ticketId} marked as rejected.`
      });
      await fetchTickets();
    } catch (err) {
      setNotificationBanner({
        type: "error",
        text: `Rejection failed: ${err.message}`
      });
    } finally {
      setIsRejecting(false);
    }
  };

  const pendingCount = tickets.filter((t) => t.status === "fix_ready").length;

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6 pb-24 animate-fade-up">
      {/* Telemetry Control Subheader & Real-time Metrics Deck */}
      <section className="w-full bg-surface-low p-5 rounded-xl border border-border flex flex-col gap-4">
        {/* Top Micro-Nav & System State */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-mono text-label-telemetry text-muted tracking-wider min-w-0">
            <span className="text-primary font-bold">Business Assistant</span>
            <span>/</span>
            <span className="text-accent-cyan font-bold">Support Desk</span>
            <span className="font-mono text-primary px-2 py-0.5 rounded bg-surface-container border border-border text-[11px] font-bold">
              #{selectedTicketId || "QUEUE"}
            </span>
            <span className="hidden md:inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container text-accent-cyan text-[11px] font-bold">
              <Terminal className="w-3.5 h-3.5 stroke-[2]" />
              AUTONOMOUS TRIAGE ENGINE
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-surface-container border border-accent-lime/40">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-lime opacity-80" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-lime" />
              </span>
              <span className="font-mono text-[11px] text-accent-lime uppercase font-bold tracking-wider">
                ACTIVE TRIAGE GRAPH
              </span>
            </div>

            <button
              onClick={fetchTickets}
              className="p-1.5 rounded hover:bg-surface-container text-muted hover:text-primary transition-colors border border-border"
              title="Refresh tickets"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingTickets ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* 4 KPI Strips Grid (Strictly Live Data) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <div className="bg-surface p-4 rounded-xl border border-border flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="font-mono text-label-telemetry text-muted uppercase tracking-wider font-bold">
                Total Backlog
              </span>
              <span className="w-2 h-2 rounded-full bg-accent-cyan" />
            </div>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="font-mono text-metric-display text-primary font-bold">
                {tickets.length}
              </span>
              <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-accent-cyan/15 text-accent-cyan font-bold">
                ACTIVE
              </span>
            </div>
          </div>

          <div className="bg-surface p-4 rounded-xl border border-border flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="font-mono text-label-telemetry text-muted uppercase tracking-wider font-bold">
                Autonomous Fix Rate
              </span>
              <span className="w-2 h-2 rounded-full bg-accent-lime" />
            </div>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="font-mono text-metric-display text-primary font-bold">
                {tickets.length > 0
                  ? `${Math.round(
                      (tickets.filter((t) => t.status === "done" || t.status === "approved").length /
                        tickets.length) *
                        100
                    )}%`
                  : "0%"}
              </span>
              <span className="font-mono text-[10px] text-accent-emerald font-bold">
                {tickets.filter((t) => t.status === "done").length} APPLIED
              </span>
            </div>
          </div>

          <div className="bg-surface p-4 rounded-xl border border-border flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="font-mono text-label-telemetry text-muted uppercase tracking-wider font-bold">
                Sandbox Latency
              </span>
              <span className="w-2 h-2 rounded-full bg-accent-amber" />
            </div>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="font-mono text-metric-display text-primary font-bold">
                {selectedTicket?.sandbox_diff?.latency ? `${selectedTicket.sandbox_diff.latency}s` : "0.8s"}
              </span>
              <span className="font-mono text-[10px] text-muted font-bold">ISOLATED DB</span>
            </div>
          </div>

          <div className="bg-surface p-4 rounded-xl border border-border flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="font-mono text-label-telemetry text-muted uppercase tracking-wider font-bold">
                Needs Approval
              </span>
              <span className="w-2 h-2 rounded-full bg-accent-lime" />
            </div>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="font-mono text-metric-display text-primary font-bold">
                {pendingCount}
              </span>
              <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-accent-lime/20 text-primary border border-accent-lime/40 font-bold">
                HITL REQUIRED
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Notification Banner */}
      {notificationBanner && (
        <div
          className={`p-3 rounded-lg border flex items-center justify-between font-body text-xs font-medium ${
            notificationBanner.type === "success"
              ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald"
              : "bg-accent-crimson/10 border-accent-crimson/30 text-accent-crimson"
          }`}
        >
          <div className="flex items-center gap-2">
            {notificationBanner.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 stroke-[2.2]" />
            ) : (
              <AlertCircle className="w-4 h-4 stroke-[2.2]" />
            )}
            <span>{notificationBanner.text}</span>
          </div>
          <button
            onClick={() => setNotificationBanner(null)}
            className="hover:underline font-mono text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Two-Pane Workspace: Left Backlog (col-span-4), Right Remediation Detail (col-span-8) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 rounded-xl border border-border overflow-hidden min-h-[750px] lg:h-[820px] bg-surface shadow-xs">
        {/* Left Column: Ticket List */}
        <div className="lg:col-span-4 h-full overflow-hidden border-b lg:border-b-0 lg:border-r border-border">
          <TicketList
            tickets={tickets}
            selectedTicketId={selectedTicketId}
            onSelectTicket={(id) => setSelectedTicketId(id)}
            filterStatus={filterStatus}
            onChangeFilter={(f) => setFilterStatus(f)}
            onOpenNewTicketModal={() => setIsModalOpen(true)}
          />
        </div>

        {/* Right Column: Ticket Detail */}
        <div className="lg:col-span-8 h-full overflow-hidden">
          <TicketDetail
            ticket={selectedTicket}
            isLoading={isLoadingDetail}
            onApprove={(id) => handleApprove(id)}
            onReject={(id, reason) => handleReject(id, reason)}
            isApproving={isApproving}
            isRejecting={isRejecting}
          />
        </div>
      </div>

      {/* Simulate Client Ticket Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            onClick={() => setIsModalOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
          />

          <div className="relative w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl p-5 z-10 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-accent-lime" />
                <h3 className="font-headline text-body-lg font-bold text-primary">
                  Simulate Client Problem Report
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded text-muted hover:text-primary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick Presets */}
            <div className="space-y-2">
              <span className="font-mono text-label-telemetry uppercase text-muted font-bold">
                Quick Incident Presets:
              </span>
              <div className="space-y-1.5">
                {PRESET_CLIENT_MESSAGES.map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      handleSendMessage({
                        sender: preset.sender,
                        sender_email: preset.email,
                        channel: preset.channel,
                        message: preset.message
                      });
                    }}
                    className="w-full text-left p-2.5 rounded bg-surface-container hover:bg-surface-container-high border border-border text-xs flex items-center justify-between group transition-colors"
                  >
                    <div className="min-w-0 pr-2">
                      <div className="font-bold text-primary text-[12px] group-hover:text-accent-cyan transition-colors">
                        {preset.label}
                      </div>
                      <div className="font-mono text-[10px] text-muted truncate">
                        {preset.message}
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-muted group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0" />
                  </button>
                ))}
              </div>
            </div>

            {/* Or custom message */}
            <div className="space-y-2 pt-2 border-t border-border">
              <span className="font-mono text-label-telemetry uppercase text-muted font-bold">
                Or Write Custom Message:
              </span>
              <textarea
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                placeholder="Type client issue description..."
                rows={3}
                className="w-full bg-surface-container border border-border rounded-lg p-2.5 text-xs text-primary placeholder:text-muted focus:outline-none focus:border-accent-cyan font-sans"
              />
              <button
                onClick={() => {
                  if (!customMessage.trim()) return;
                  handleSendMessage({
                    sender: customSender,
                    sender_email: customEmail,
                    channel: customChannel,
                    message: customMessage.trim()
                  });
                }}
                disabled={isSubmittingMessage || !customMessage.trim()}
                className="w-full py-2 rounded-lg bg-accent-lime text-accent-lime-contrast font-headline text-xs font-bold hover:bg-accent-lime/90 disabled:opacity-40 transition-all flex items-center justify-center gap-2"
              >
                {isSubmittingMessage ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                <span>Dispatch to Autonomous Support Graph</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
