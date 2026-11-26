"use client";

import React, { useState, useEffect } from "react";
import { X, Copy, Check, ExternalLink, ShieldAlert } from "lucide-react";
import Stamp from "./Stamp";
import SqlBlock from "./SqlBlock";
import DataTable from "./DataTable";
import { getChannelInfo } from "./Strip";
import { formatClockTime } from "../lib/formatters";

const PIPELINE_STEPS = [
  { key: "classify", label: "01 Classify" },
  { key: "investigate", label: "02 Investigate" },
  { key: "propose_fix", label: "03 Propose Fix" },
  { key: "test_fix", label: "04 Sandbox Test" },
  { key: "await_approval", label: "05 Human Gate" },
  { key: "apply_fix", label: "06 Apply" },
  { key: "notify", label: "07 Notify" },
];

function getSafeExternalUrl(raw) {
  if (!raw || typeof raw !== "string") return null;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

function DiffViewer({ diffText }) {
  if (!diffText) return null;
  const lines = diffText.split("\n");
  return (
    <div className="border border-grid rounded-xs overflow-hidden bg-raised font-mono text-xs">
      <div className="px-3 py-1.5 border-b border-grid bg-sunken font-bold text-[10.5px] uppercase tracking-wider text-muted">
        Unified Diff Proposal
      </div>
      <pre className="p-3 overflow-x-auto leading-relaxed m-0 text-[11.5px]">
        {lines.map((line, i) => {
          const isAdd = line.startsWith("+") && !line.startsWith("+++");
          const isDel = line.startsWith("-") && !line.startsWith("---");
          const isHunk = line.startsWith("@@");
          return (
            <div
              key={i}
              className={`px-1.5 rounded-xs ${
                isAdd
                  ? "bg-sage-tint text-sage-ink font-semibold"
                  : isDel
                  ? "bg-seal-tint text-seal-ink font-semibold"
                  : isHunk
                  ? "text-route-data-ink font-bold"
                  : "text-ink"
              }`}
            >
              {line || " "}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

export default function TicketDetail({
  ticket,
  isOpen = false,
  isLoading = false,
  onClose = () => {},
  onApprove = () => {},
  onReject = () => {},
  isApproving = false,
  isRejecting = false,
  stampAnimate = false,
}) {
  const [confirmingApprove, setConfirmingApprove] = useState(false);
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [copiedFix, setCopiedFix] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isFlagged = Boolean(ticket?.is_flagged || ticket?.status === "flagged");
  const isPendingApproval = ticket?.status === "fix_ready" && !isFlagged;
  const isApplied = ticket?.status === "done" || ticket?.status === "approved";
  const isRejected = ticket?.status === "rejected";

  const clientName =
    ticket?.client_name || ticket?.sender_name || ticket?.sender || "Client";
  const clientEmail =
    ticket?.client_email || ticket?.sender_email || "—";
  const messageContent =
    ticket?.message || ticket?.original_message || ticket?.issue || "";

  const chInfo = getChannelInfo(ticket?.channel);
  const ChannelIcon = chInfo.Icon;

  const investigationText =
    typeof ticket?.investigation === "string"
      ? ticket.investigation
      : ticket?.investigation?.root_cause ||
        ticket?.investigation?.recommendation ||
        ticket?.root_cause ||
        "Investigation pending or completed without summary.";

  const proposedFix = ticket?.proposed_fix || {};
  const unifiedDiff =
    typeof proposedFix === "object" ? proposedFix.unified_diff : null;
  const sqlPatch =
    typeof proposedFix === "object" ? proposedFix.sql_patch : null;
  const fallbackPatchText =
    typeof proposedFix === "string"
      ? proposedFix
      : proposedFix.patch || proposedFix.code || proposedFix.answer_draft || "";

  const copyPayload = unifiedDiff || sqlPatch || fallbackPatchText;

  const sandboxDiff = ticket?.sandbox_diff || {};
  const beforeCounts = sandboxDiff.before_counts || null;
  const afterCounts = sandboxDiff.after_counts || null;
  const sandboxRows = [];
  if (beforeCounts || afterCounts) {
    const keys = Array.from(
      new Set([
        ...Object.keys(beforeCounts || {}),
        ...Object.keys(afterCounts || {}),
      ])
    );
    keys.forEach((k) => {
      sandboxRows.push({
        metric: k.replace(/_/g, " "),
        before: beforeCounts?.[k] ?? "—",
        after: afterCounts?.[k] ?? "—",
      });
    });
    if (typeof sandboxDiff.rows_affected === "number") {
      sandboxRows.push({
        metric: "rows affected",
        before: 0,
        after: sandboxDiff.rows_affected,
      });
    }
  }

  const handleCopyFix = () => {
    if (!copyPayload) return;
    navigator.clipboard.writeText(copyPayload);
    setCopiedFix(true);
    setTimeout(() => setCopiedFix(false), 1800);
  };

  const stampVariant = isFlagged
    ? "flagged"
    : isApplied
    ? "applied"
    : isRejected
    ? "rejected"
    : isPendingApproval
    ? "needs_review"
    : ticket?.status === "investigating"
    ? "investigating"
    : "new";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-ink/45"
      role="dialog"
      aria-modal="true"
      aria-label={ticket ? `Ticket ${ticket.id} inspection sheet` : "Ticket sheet"}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl h-full bg-paper border-s border-grid flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sheet Header */}
        <header className="px-5 py-3.5 border-b border-grid bg-raised flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0 flex-wrap">
            <span className="font-mono text-sm font-bold text-ink tabular-mono">
              #{ticket?.id || "..."}
            </span>
            {ticket?.classification && (
              <span className="px-2 py-0.5 rounded-xs border border-grid bg-sunken font-mono text-[10.5px] font-bold uppercase text-ink">
                {String(ticket.classification).replace(/_/g, " ")}
              </span>
            )}
            <span className="font-mono text-[11px] text-muted tabular-mono">
              Confidence:{" "}
              {ticket?.confidence ? `${Math.round(ticket.confidence * 100)}%` : "—"}
            </span>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Stamp
              variant={stampVariant}
              shape="square"
              size="md"
              animate={stampAnimate}
            />
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xs border border-grid bg-raised text-ink hover:border-ink cursor-pointer"
              aria-label="Close ticket sheet"
            >
              <X className="w-4 h-4" strokeWidth={1.6} />
            </button>
          </div>
        </header>

        {/* Sheet Body */}
        {isLoading || !ticket ? (
          <div className="p-6 space-y-3 font-mono text-xs text-muted">
            Loading ticket record and sandbox evidence...
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Title */}
            <div>
              <h2 className="font-serif text-xl font-semibold text-ink leading-snug break-words">
                {ticket.title || ticket.issue || messageContent || "Support Ticket"}
              </h2>
            </div>

            {/* 1. Original Message (strictly escaped text node, never HTML) */}
            <section className="p-3.5 rounded-xs border border-grid bg-raised space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-grid font-mono text-[11px]">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-bold text-ink truncate">{clientName}</span>
                  <span className="text-muted truncate">&lt;{clientEmail}&gt;</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs border border-grid bg-sunken text-ink font-bold">
                    <ChannelIcon className="w-3 h-3" strokeWidth={1.6} />
                    {chInfo.label}
                  </span>
                  {getSafeExternalUrl(ticket.thread_url) && (
                    <a
                      href={getSafeExternalUrl(ticket.thread_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-route-data-ink underline font-semibold"
                    >
                      <span>Thread</span>
                      <ExternalLink className="w-3 h-3" strokeWidth={1.6} />
                    </a>
                  )}
                </div>
              </div>

              <div className="font-sans text-sm text-ink leading-relaxed whitespace-pre-wrap break-words bg-sunken/50 p-3 rounded-xs border border-grid/70">
                {messageContent}
              </div>
            </section>

            {/* Security Flag Alert */}
            {isFlagged && (
              <section
                role="alert"
                className="p-3.5 rounded-xs border border-seal bg-seal-tint space-y-1"
              >
                <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase text-seal-ink">
                  <ShieldAlert className="w-4 h-4" strokeWidth={1.6} />
                  <span>Flagged Untrusted Message</span>
                </div>
                <p className="text-xs text-ink leading-relaxed">
                  {ticket.flag_reason ||
                    "Prompt-injection or unsafe directive detected. Automated execution was blocked."}
                </p>
              </section>
            )}

            {/* 2. Step Timeline */}
            <section className="space-y-2">
              <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
                Step Timeline
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {PIPELINE_STEPS.map((st, idx) => {
                  const completed =
                    isApplied ||
                    idx < 4 ||
                    (idx === 4 && (isPendingApproval || isRejected));
                  const active = isPendingApproval && idx === 4;
                  return (
                    <div
                      key={st.key}
                      className={`px-2.5 py-1.5 rounded-xs border font-mono text-[10.5px] ${
                        active
                          ? "border-ink bg-highlighter-wash font-bold text-ink"
                          : completed
                          ? "border-grid bg-raised text-ink"
                          : "border-grid bg-sunken/40 text-muted"
                      }`}
                    >
                      <div className="truncate font-semibold">{st.label}</div>
                      <div className="text-[9.5px] text-muted">
                        {active
                          ? "Awaiting gate"
                          : isApplied && idx >= 5
                          ? "Complete"
                          : completed
                          ? "Done"
                          : "Queued"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* 3. Root Cause Investigation */}
            <section className="p-3.5 rounded-xs border border-grid bg-raised space-y-1.5">
              <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
                Investigation Summary
              </div>
              <p className="font-sans text-sm text-ink leading-relaxed break-words">
                {investigationText}
              </p>
            </section>

            {/* 4. Proposed Fix Diff / SQL Patch */}
            {!isFlagged && (unifiedDiff || sqlPatch || fallbackPatchText) && (
              <section className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
                    Proposed Fix
                  </span>
                  {copyPayload && (
                    <button
                      type="button"
                      onClick={handleCopyFix}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs border border-grid bg-raised font-mono text-[10.5px] text-ink cursor-pointer"
                    >
                      {copiedFix ? (
                        <>
                          <Check className="w-3 h-3 text-sage-ink" strokeWidth={1.8} />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" strokeWidth={1.6} />
                          <span>Copy Fix</span>
                        </>
                      )}
                    </button>
                  )}
                </div>

                {unifiedDiff && <DiffViewer diffText={unifiedDiff} />}
                {sqlPatch && <SqlBlock sql={sqlPatch} label="Proposed SQL Remediation" />}
                {!unifiedDiff && !sqlPatch && fallbackPatchText && (
                  <pre className="p-3 rounded-xs border border-grid bg-raised font-mono text-xs text-ink whitespace-pre-wrap break-words">
                    {fallbackPatchText}
                  </pre>
                )}
              </section>
            )}

            {/* 5. Sandbox Before / After Table */}
            {(sandboxRows.length > 0 || (Array.isArray(sandboxDiff.sample_diff) && sandboxDiff.sample_diff.length > 0)) && (
              <section className="space-y-2">
                <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
                  Sandbox Before / After Verification
                </div>
                {sandboxRows.length > 0 && (
                  <DataTable
                    rows={sandboxRows}
                    maxRows={10}
                    title={`Sandbox (${sandboxDiff.target_table || "isolated"})`}
                  />
                )}
                {Array.isArray(sandboxDiff.sample_diff) && sandboxDiff.sample_diff.length > 0 && (
                  <DataTable
                    rows={sandboxDiff.sample_diff}
                    maxRows={5}
                    title="Sandbox Row Sample"
                  />
                )}
              </section>
            )}

            {/* 6. Deliberate Human-in-the-Loop Approval Gate */}
            {isPendingApproval && (
              <section className="p-4 rounded-xs border-[1.5px] border-seal bg-raised paper-stack space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-seal-ink">
                    Human Approval Required
                  </div>
                  <span className="font-mono text-[10.5px] px-2 py-0.5 rounded-xs border border-grid bg-sunken text-ink tabular-mono">
                    Token: {ticket.approval_token || "PENDING"}
                  </span>
                </div>

                <p className="text-xs text-muted leading-relaxed">
                  Verified on an isolated sandbox without modifying production tables. Review the diff and before/after table above before approving.
                </p>

                {!confirmingApprove ? (
                  <div className="flex flex-wrap items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => setConfirmingApprove(true)}
                      disabled={isApproving}
                      className="px-4 py-2 rounded-xs border border-seal bg-seal text-seal-on font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 cursor-pointer disabled:opacity-50"
                    >
                      Approve &amp; Apply Fix
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRejectInput(!showRejectInput)}
                      className="px-3.5 py-2 rounded-xs border border-grid bg-raised text-ink hover:border-seal font-mono text-xs font-semibold cursor-pointer"
                    >
                      Reject
                    </button>
                  </div>
                ) : (
                  <div className="p-3 rounded-xs border border-seal bg-seal-tint space-y-2.5">
                    <div className="font-mono text-xs font-bold text-seal-ink">
                      Confirm production commit? This applies the verified remediation and notifies the sender.
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onApprove(ticket.id)}
                        disabled={isApproving}
                        className="px-3.5 py-1.5 rounded-xs border border-seal bg-seal text-seal-on font-mono text-xs font-bold uppercase tracking-wider cursor-pointer disabled:opacity-50"
                      >
                        {isApproving ? "Applying..." : "Confirm Apply"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmingApprove(false)}
                        disabled={isApproving}
                        className="px-3 py-1.5 rounded-xs border border-grid bg-raised text-ink font-mono text-xs cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {showRejectInput && (
                  <div className="pt-2 border-t border-grid flex flex-col sm:flex-row gap-2">
                    <label htmlFor="reject-reason-input" className="sr-only">
                      Rejection reason
                    </label>
                    <input
                      id="reject-reason-input"
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Optional rejection note..."
                      className="flex-1 px-2.5 py-1.5 rounded-xs border border-grid bg-paper text-xs text-ink font-mono focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => onReject(ticket.id, rejectReason)}
                      disabled={isRejecting}
                      className="px-3 py-1.5 rounded-xs border border-seal bg-seal text-seal-on font-mono text-xs font-bold cursor-pointer disabled:opacity-50 shrink-0"
                    >
                      {isRejecting ? "Rejecting..." : "Confirm Reject"}
                    </button>
                  </div>
                )}
              </section>
            )}

            {/* Applied / Rejected Outcome Seal */}
            {(isApplied || isRejected) && (
              <section className="p-3.5 rounded-xs border border-grid bg-raised flex items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="font-mono text-xs font-bold text-ink">
                    {isApplied
                      ? "Remediation Applied & Sender Notified"
                      : "Remediation Rejected by Operator"}
                  </div>
                  <div className="font-mono text-[11px] text-muted">
                    {isApplied
                      ? "Audit trail recorded; production synchronized."
                      : "No production changes applied."}
                  </div>
                </div>
                <Stamp
                  variant={isApplied ? "approved" : "rejected"}
                  shape="circle"
                  size="md"
                  animate={stampAnimate}
                />
              </section>
            )}

            {/* Outbound Reply */}
            {ticket.reply_message && (
              <section className="p-3.5 rounded-xs border border-grid bg-raised space-y-1.5">
                <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
                  Outbound Thread Reply
                </div>
                <p className="font-sans text-xs text-ink leading-relaxed whitespace-pre-wrap break-words">
                  {ticket.reply_message}
                </p>
              </section>
            )}

            {/* Audit Trail */}
            {Array.isArray(ticket.audit_trail) && ticket.audit_trail.length > 0 && (
              <section className="space-y-2">
                <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-muted">
                  Audit Log
                </div>
                <div className="border border-grid rounded-xs bg-raised divide-y divide-grid font-mono text-[11px]">
                  {ticket.audit_trail.map((entry, idx) => (
                    <div
                      key={entry.id || idx}
                      className="px-3 py-2 flex items-center justify-between gap-2"
                    >
                      <div className="min-w-0">
                        <span className="font-bold text-ink">{entry.action}</span>
                        <span className="text-muted ml-2">by {entry.performed_by}</span>
                      </div>
                      <span className="text-muted tabular-mono shrink-0">
                        {formatClockTime(entry.timestamp)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
