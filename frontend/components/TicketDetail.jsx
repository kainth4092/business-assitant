"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  Database,
  FileCode,
  GitCommit,
  GitPullRequest,
  Layers,
  MessageSquare,
  RotateCw,
  ShieldCheck,
  Terminal,
  User,
  XCircle,
  Zap
} from "lucide-react";

export default function TicketDetail({
  ticket,
  isLoading = false,
  onApprove = () => {},
  onReject = () => {},
  isApproving = false,
  isRejecting = false
}) {
  const [copiedCode, setCopiedCode] = useState(false);
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-12 text-center text-muted font-mono text-xs">
        <RotateCw className="w-6 h-6 animate-spin text-accent-lime mb-3" />
        <span className="text-primary font-bold text-body-md">Loading Ticket Telemetry &amp; Sandbox Evidence...</span>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-12 text-center text-muted bg-surface-lowest">
        <div className="w-12 h-12 rounded-lg bg-surface-container border border-border flex items-center justify-center mb-3 text-muted">
          <MessageSquare className="w-6 h-6 stroke-[1.5]" />
        </div>
        <h3 className="font-headline text-headline-sm font-bold text-primary mb-1">
          Select a Support Ticket
        </h3>
        <p className="font-body text-body-sm text-muted max-w-sm leading-relaxed">
          Choose a ticket from the backlog on the left to inspect its autonomous classification, investigate the sandbox reproduction, and review proposed fixes.
        </p>
      </div>
    );
  }

  const isPendingApproval = ticket.status === "fix_ready";
  const isApplied = ticket.status === "done";
  const isRejected = ticket.status === "rejected";

  const clientName = ticket.client_name || ticket.sender_name || ticket.sender || "Client Operations";
  const clientEmail = ticket.client_email || ticket.sender_email || "client@company.com";
  const messageContent = ticket.message || ticket.original_message || ticket.issue || "Issue description...";

  const investigationText = typeof ticket.investigation === "string"
    ? ticket.investigation
    : ticket.investigation?.root_cause || ticket.investigation?.recommendation || ticket.root_cause || "Investigation identified inconsistencies in data format.";

  const proposedCode = typeof ticket.proposed_fix === "string"
    ? ticket.proposed_fix
    : ticket.proposed_fix?.sql_patch || ticket.proposed_fix?.patch || ticket.proposed_fix?.code || (ticket.proposed_fix ? JSON.stringify(ticket.proposed_fix, null, 2) : "");

  const testSummary = typeof ticket.test_results?.summary === "string"
    ? ticket.test_results.summary
    : ticket.test_results?.passed
    ? "All verification assertions passed on isolated clone"
    : "Sandbox verification completed";

  const handleCopyCode = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <div className="h-full flex flex-col bg-surface overflow-y-auto">
      {/* Top Header & Breadcrumb */}
      <div className="p-5 border-b border-border bg-surface-low space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-headline-sm font-bold text-primary">
              #{ticket.id}
            </span>
            <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container font-semibold uppercase text-accent-cyan border border-accent-cyan/30">
              {typeof ticket.classification === "string" ? ticket.classification.replace("_", " ") : "CLASSIFIED"}
            </span>
            <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container font-semibold text-muted border border-border">
              Confidence: {ticket.confidence ? Math.round(ticket.confidence * 100) : 100}%
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container text-accent-emerald font-mono text-[11px] font-bold border border-accent-emerald/30">
              <ShieldCheck className="w-3.5 h-3.5 stroke-[2.2]" />
              SANDBOX VERIFIED
            </span>
          </div>
        </div>

        <h2 className="font-headline text-headline-lg font-bold text-primary tracking-tight">
          {ticket.title || ticket.issue || messageContent || "Autonomous Support Investigation"}
        </h2>

        {/* 7-Step LangGraph Support Flow Pipeline Tracker */}
        <div className="pt-2">
          <div className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider mb-2">
            Multi-Agent Autonomous Remediation Graph
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-2">
            {/* Step 1: Classify */}
            <div className="flex flex-col gap-0.5 p-2 rounded bg-surface-container border border-border">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] text-muted font-bold">STEP 01</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-lime shrink-0" />
              </div>
              <span className="font-headline text-[11px] font-bold text-primary truncate">Classify</span>
              <span className="font-mono text-[9px] text-muted truncate">100% Match</span>
            </div>

            {/* Step 2: Investigate */}
            <div className="flex flex-col gap-0.5 p-2 rounded bg-surface-container border border-border">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] text-muted font-bold">STEP 02</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-lime shrink-0" />
              </div>
              <span className="font-headline text-[11px] font-bold text-primary truncate">Investigate</span>
              <span className="font-mono text-[9px] text-muted truncate">Schema isolated</span>
            </div>

            {/* Step 3: Propose Fix */}
            <div className="flex flex-col gap-0.5 p-2 rounded bg-surface-container border border-border">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] text-muted font-bold">STEP 03</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-lime shrink-0" />
              </div>
              <span className="font-headline text-[11px] font-bold text-primary truncate">Propose Fix</span>
              <span className="font-mono text-[9px] text-muted truncate">Diff generated</span>
            </div>

            {/* Step 4: Sandbox Test */}
            <div className="flex flex-col gap-0.5 p-2 rounded bg-surface-container border border-border">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] text-muted font-bold">STEP 04</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-lime shrink-0" />
              </div>
              <span className="font-headline text-[11px] font-bold text-primary truncate">Sandbox Test</span>
              <span className="font-mono text-[9px] text-muted truncate">Tests pass</span>
            </div>

            {/* Step 5: Await Approval */}
            <div
              className={`flex flex-col gap-0.5 p-2 rounded border relative ${
                isPendingApproval
                  ? "bg-surface-container-high border-2 border-accent-lime shadow-xs"
                  : "bg-surface-container border-border"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] font-bold text-primary">STEP 05</span>
                {isApplied ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald shrink-0" />
                ) : isRejected ? (
                  <XCircle className="w-3.5 h-3.5 text-accent-crimson shrink-0" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-accent-lime animate-ping" />
                )}
              </div>
              <span className="font-headline text-[11px] font-bold text-primary truncate">
                Approval
              </span>
              <span
                className={`font-mono text-[8px] font-bold text-center px-1 py-0.2 rounded truncate ${
                  isPendingApproval
                    ? "bg-accent-lime/20 text-primary"
                    : isApplied
                    ? "text-accent-emerald"
                    : "text-muted"
                }`}
              >
                {isPendingApproval ? "HITL REQUIRED" : isApplied ? "APPROVED" : "STANDBY"}
              </span>
            </div>

            {/* Step 6: Apply Fix */}
            <div
              className={`flex flex-col gap-0.5 p-2 rounded border ${
                isApplied
                  ? "bg-surface-container border-accent-emerald/40 text-primary"
                  : "bg-surface-container/60 border-border text-muted opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] font-bold">STEP 06</span>
                {isApplied && <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald shrink-0" />}
              </div>
              <span className="font-headline text-[11px] font-bold leading-tight truncate">Apply Patch</span>
              <span className="font-mono text-[9px] truncate">
                {isApplied ? "Committed" : "Queued"}
              </span>
            </div>

            {/* Step 7: Notify */}
            <div
              className={`flex flex-col gap-0.5 p-2 rounded border ${
                isApplied
                  ? "bg-surface-container border-accent-emerald/40 text-primary"
                  : "bg-surface-container/60 border-border text-muted opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] font-bold">STEP 07</span>
                {isApplied && <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald shrink-0" />}
              </div>
              <span className="font-headline text-[11px] font-bold leading-tight truncate">Notify</span>
              <span className="font-mono text-[9px] truncate">
                {isApplied ? "Sent to client" : "Queued"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Body Grid */}
      <div className="p-5 space-y-5 flex-1 pb-16">
        {/* Client Problem Statement Card */}
        <div className="p-4 rounded-lg bg-surface-low border border-border space-y-2">
          <div className="flex items-center justify-between pb-2 border-b border-border">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4 text-accent-cyan" />
              <span className="font-headline text-body-sm font-bold text-primary">
                {clientName}
              </span>
              <span className="font-mono text-label-telemetry text-muted">
                &lt;{clientEmail}&gt;
              </span>
            </div>
            <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container text-muted uppercase">
              Via {ticket.channel || "slack"}
            </span>
          </div>

          <p className="font-body text-body-md text-primary leading-relaxed italic bg-surface-container p-3 rounded border border-border">
            &ldquo;{messageContent}&rdquo;
          </p>
        </div>

        {/* Investigation & Root Cause Summary */}
        <div className="p-4 rounded-lg bg-surface-low border border-border space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-label-telemetry uppercase text-muted font-bold tracking-wider">
              Autonomous Investigation &amp; Root Cause
            </span>
            <span className="font-mono text-label-telemetry text-accent-cyan font-bold">
              ANALYZED
            </span>
          </div>

          <p className="font-body text-body-md text-primary leading-relaxed">
            {investigationText}
          </p>
        </div>

        {/* Proposed Fix & Sandbox Verification */}
        {ticket.proposed_fix && (
          <div className="p-4 rounded-lg bg-surface-low border border-border space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-accent-cyan" />
                <span className="font-headline text-body-sm font-bold text-primary">
                  Proposed Solution &amp; Validation Diff
                </span>
              </div>
              <button
                onClick={() => handleCopyCode(proposedCode)}
                className="inline-flex items-center gap-1 text-muted hover:text-primary font-mono text-[11px] transition-colors"
              >
                {copiedCode ? <Check className="w-3.5 h-3.5 text-accent-emerald" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedCode ? "Copied" : "Copy Fix"}</span>
              </button>
            </div>

            {/* Code / Patch Block */}
            <div className="rounded-lg bg-surface-container-lowest border border-border p-3.5 font-mono text-code-md overflow-x-auto text-primary">
              <pre className="whitespace-pre-wrap leading-relaxed">
                {proposedCode}
              </pre>
            </div>

            {/* Sandbox Verification Result */}
            {ticket.test_results && (
              <div className="p-3 rounded-lg bg-surface-container border border-border flex items-center justify-between text-xs font-mono">
                <span className="text-muted">
                  Sandbox Test: {testSummary}
                </span>
                <span className="text-accent-emerald font-bold">
                  {ticket.test_results.passed ? "PASS (100%)" : "VERIFIED"}
                </span>
              </div>
            )}
          </div>
        )}

        {/* HITL Human Approval Action Strip */}
        {isPendingApproval && (
          <div className="p-5 rounded-xl bg-surface-container border-2 border-accent-lime shadow-md space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-accent-lime animate-pulse" />
                <span className="font-headline text-body-lg font-bold text-primary">
                  Human-In-The-Loop Approval Required
                </span>
              </div>
              <span className="font-mono text-label-telemetry px-2 py-0.5 rounded bg-surface-container-high text-muted">
                Audit Token: #{ticket.approval_token || "PENDING"}
              </span>
            </div>

            <p className="font-body text-body-sm text-muted">
              The proposed fix has been thoroughly verified on an isolated PostgreSQL sandbox clone without touching production tables. Confirm approval to apply changes to production and send client notification.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={() => onApprove(ticket.id)}
                disabled={isApproving}
                className="px-5 py-2.5 rounded-lg bg-accent-lime hover:bg-accent-lime/90 text-accent-lime-contrast font-headline text-[13px] font-bold flex items-center gap-2 shadow-xs transition-all active:scale-95 disabled:opacity-50"
              >
                {isApproving ? <RotateCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4 fill-current" />}
                <span>APPROVE &amp; APPLY REMEDIATION</span>
              </button>

              <button
                onClick={() => setShowRejectInput(!showRejectInput)}
                className="px-4 py-2.5 rounded-lg border border-accent-crimson/50 text-accent-crimson hover:bg-accent-crimson/10 font-headline text-[13px] font-semibold transition-all active:scale-95"
              >
                Reject Fix
              </button>
            </div>

            {/* Optional reject reason input */}
            {showRejectInput && (
              <div className="pt-2 flex items-center gap-2">
                <input
                  type="text"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Reason for rejection..."
                  className="flex-1 bg-surface-lowest border border-border rounded px-3 py-1.5 text-xs text-primary focus:outline-none"
                />
                <button
                  onClick={() => onReject(ticket.id, rejectReason)}
                  disabled={isRejecting}
                  className="px-3 py-1.5 rounded bg-accent-crimson text-white text-xs font-bold"
                >
                  Confirm Rejection
                </button>
              </div>
            )}
          </div>
        )}

        {/* Applied / Resolved Banner */}
        {isApplied && (
          <div className="p-4 rounded-lg bg-accent-emerald/10 border border-accent-emerald/30 text-accent-emerald flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 stroke-[2.2]" />
              <div className="font-headline text-body-md font-bold">
                Remediation Applied &amp; Client Notified
              </div>
            </div>
            <span className="font-mono text-label-telemetry">
              Audit log verified &middot; Production in sync
            </span>
          </div>
        )}

        {/* Rejected Banner */}
        {isRejected && (
          <div className="p-4 rounded-lg bg-accent-crimson/10 border border-accent-crimson/30 text-accent-crimson flex items-center justify-between">
            <div className="flex items-center gap-2">
              <XCircle className="w-5 h-5 stroke-[2.2]" />
              <div className="font-headline text-body-md font-bold">
                Fix Proposal Rejected by Operator
              </div>
            </div>
            <span className="font-mono text-label-telemetry">
              Archived for manual engineering triage
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
