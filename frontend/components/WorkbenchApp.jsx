"use client";

import React, { useState, useEffect, useRef, useSyncExternalStore } from "react";
import {
  Menu,
  PanelRight,
  Upload,
  ArrowLeft,
  Plus,
  Search,
} from "lucide-react";

import Spine from "./Spine";
import LogEntry from "./LogEntry";
import Margin from "./Margin";
import EmptyState from "./EmptyState";
import Composer from "./Composer";
import Timeline from "./Timeline";
import DataQualityView from "./DataQualityView";
import DocumentsView from "./DocumentsView";
import SupportDeskView from "./SupportDeskView";
import ProjectsView from "./ProjectsView";
import AddDataModal from "./AddDataModal";
import CommandPalette from "./CommandPalette";
import KeyboardHelpModal from "./KeyboardHelpModal";
import ErrorState from "./ErrorState";
import { streamAgentChat, startSafeViewTransition } from "../lib/sseStream";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function safeJsonParse(value, fallback) {
  if (typeof value !== "string") return value ?? fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function subscribeXl(callback) {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia("(min-width: 1280px)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getXlSnapshot() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(min-width: 1280px)").matches;
}

function getXlServerSnapshot() {
  return true;
}

export default function WorkbenchApp() {
  const isDesktopXl = useSyncExternalStore(
    subscribeXl,
    getXlSnapshot,
    getXlServerSnapshot
  );
  const [activeTab, setActiveTab] = useState("chat");
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isEvidencePanelOpen, setIsEvidencePanelOpen] = useState(false);

  const [selectedRoute, setSelectedRoute] = useState("auto");
  const [inputQuery, setInputQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeLiveStep, setActiveLiveStep] = useState(null);
  const [liveMessage, setLiveMessage] = useState(null);
  const [threadId, setThreadId] = useState(null);

  const [messages, setMessages] = useState([]);
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState(null);
  const [highlightedCitationIndex, setHighlightedCitationIndex] = useState(null);

  const [systemHealth, setSystemHealth] = useState(null);
  const [isStatusLoading, setIsStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState(null);
  const [dataQualityReport, setDataQualityReport] = useState(null);
  const [dataQualityError, setDataQualityError] = useState(null);
  const [indexedSources, setIndexedSources] = useState([]);
  const [sourcesError, setSourcesError] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [supportTickets, setSupportTickets] = useState([]);
  const [pendingTicketsCount, setPendingTicketsCount] = useState(0);
  const [isDataQualityLoading, setIsDataQualityLoading] = useState(false);
  const [isSourcesLoading, setIsSourcesLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);
  const [lastFailedQuery, setLastFailedQuery] = useState(null);

  const [isAddDataModalOpen, setIsAddDataModalOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isKeyboardHelpOpen, setIsKeyboardHelpOpen] = useState(false);
  const [externalTicketId, setExternalTicketId] = useState(null);
  const [externalDocFile, setExternalDocFile] = useState(null);

  const messagesEndRef = useRef(null);
  const composerInputRef = useRef(null);
  const abortControllerRef = useRef(null);

  const switchTab = (nextTab) => {
    startSafeViewTransition(() => {
      setActiveTab(nextTab);
      if (nextTab !== "chat" && typeof window !== "undefined" && window.innerWidth < 1280) {
        setIsEvidencePanelOpen(false);
      }
      if (nextTab === "support-desk") {
        fetchTicketsSummary();
      } else if (nextTab === "data-quality") {
        fetchDataQuality();
      }
    });
  };

  const fetchStatus = async () => {
    setIsStatusLoading(true);
    setStatusError(null);
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (res.ok) {
        const data = await res.json();
        setSystemHealth(data);
      } else {
        throw new Error(`Status endpoint returned HTTP ${res.status}`);
      }
    } catch (e) {
      setStatusError(e.message || `Backend unreachable at ${API_BASE}`);
    } finally {
      setIsStatusLoading(false);
    }
  };

  const fetchConversations = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
      }
    } catch {
      // ignore
    }
  };

  const fetchDataQuality = async () => {
    setIsDataQualityLoading(true);
    setDataQualityError(null);
    try {
      const res = await fetch(`${API_BASE}/data-quality`);
      if (res.ok) {
        const data = await res.json();
        setDataQualityReport(data);
      } else if (res.status === 404) {
        setDataQualityReport(null);
      } else {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
    } catch (e) {
      setDataQualityError(e.message || "Could not load data quality report.");
    } finally {
      setIsDataQualityLoading(false);
    }
  };

  const fetchSources = async () => {
    setIsSourcesLoading(true);
    setSourcesError(null);
    try {
      const res = await fetch(`${API_BASE}/sources`);
      if (res.ok) {
        const data = await res.json();
        setIndexedSources(data.documents || []);
      } else {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
    } catch (e) {
      setSourcesError(e.message || "Could not load indexed documents.");
    } finally {
      setIsSourcesLoading(false);
    }
  };

  const fetchTicketsSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/support/tickets`);
      if (res.ok) {
        const data = await res.json();
        const list = data.tickets || [];
        setSupportTickets(list);
        setPendingTicketsCount(
          list.filter((t) => t.status === "fix_ready" && !t.is_flagged).length
        );
      }
    } catch {
      // ignore
    }
  };

  const handleDataReload = () => {
    fetchStatus();
    fetchDataQuality();
    fetchSources();
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/status`);
        if (cancelled) return;
        if (res.ok) {
          const statusData = await res.json();
          setSystemHealth(statusData);
          setStatusError(null);
          if ((statusData?.sales_records ?? 0) > 0) {
            const dqRes = await fetch(`${API_BASE}/data-quality`);
            if (!cancelled) {
              if (dqRes.ok) {
                setDataQualityReport(await dqRes.json());
              } else if (dqRes.status !== 404) {
                const err = await dqRes.json().catch(() => null);
                setDataQualityError(err?.detail || `HTTP ${dqRes.status}`);
              }
            }
          }
        } else {
          setStatusError(`Status endpoint returned HTTP ${res.status}`);
        }
      } catch (e) {
        if (!cancelled) {
          setStatusError(e.message || `Backend unreachable at ${API_BASE}`);
        }
      } finally {
        if (!cancelled) setIsStatusLoading(false);
      }
    })();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/sources`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          setIndexedSources(data.documents || []);
        }
      } catch (e) {
        if (!cancelled) setSourcesError(e.message || "Could not load indexed documents.");
      }
    })();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/conversations`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          setConversations(data.conversations || []);
        }
      } catch {
        // ignore
      }
    })();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/support/tickets`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          const list = data.tickets || [];
          setSupportTickets(list);
          setPendingTicketsCount(
            list.filter((t) => t.status === "fix_ready" && !t.is_flagged).length
          );
        }
      } catch {
        // ignore
      }
    })();

    const mq = window.matchMedia("(min-width: 1280px)");
    const onMqChange = (e) => {
      if (!cancelled && !e.matches) {
        setIsEvidencePanelOpen(false);
      }
    };
    mq.addEventListener("change", onMqChange);

    const rafId = window.requestAnimationFrame(() => {
      if (!cancelled && mq.matches) {
        setIsEvidencePanelOpen(true);
      }
    });

    return () => {
      cancelled = true;
      mq.removeEventListener("change", onMqChange);
      window.cancelAnimationFrame(rafId);
    };
  }, []);

  const toggleTheme = () => {
    const isDark = document.documentElement.classList.contains("dark");
    if (isDark) {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    } else {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    }
  };

  const handleNewSession = () => {
    abortControllerRef.current?.abort();
    setMessages([]);
    setActiveEvidence(null);
    setSelectedQuestionId(null);
    setHighlightedCitationIndex(null);
    setThreadId(null);
    setInputQuery("");
    setErrorBanner(null);
    setLastFailedQuery(null);
    setSelectedRoute("auto");
    setActiveTab("chat");
    if (typeof window !== "undefined" && window.innerWidth < 1280) {
      setIsEvidencePanelOpen(false);
    }
  };

  // Global keyboard-first shortcuts
  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
        return;
      }

      if (e.key === "Escape") {
        setIsMobileSidebarOpen(false);
        setIsCommandPaletteOpen(false);
        setIsKeyboardHelpOpen(false);
        if (typeof window !== "undefined" && window.innerWidth < 1280) {
          setIsEvidencePanelOpen(false);
        }
        return;
      }

      const tag = e.target?.tagName?.toLowerCase();
      const isTyping =
        tag === "input" ||
        tag === "textarea" ||
        tag === "select" ||
        e.target?.isContentEditable;

      if (isTyping || e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "?") {
        e.preventDefault();
        setIsKeyboardHelpOpen((prev) => !prev);
      } else if (e.key === "1") {
        switchTab("chat");
      } else if (e.key === "2") {
        switchTab("support-desk");
      } else if (e.key === "3") {
        switchTab("data-quality");
      } else if (e.key === "4") {
        switchTab("documents");
      } else if (e.key === "5") {
        switchTab("projects");
      } else if (e.key.toLowerCase() === "n") {
        e.preventDefault();
        handleNewSession();
        setTimeout(() => composerInputRef.current?.focus(), 20);
      } else if (e.key.toLowerCase() === "e" && activeTab === "chat") {
        e.preventDefault();
        setIsEvidencePanelOpen((prev) => !prev);
      } else if (e.key.toLowerCase() === "d") {
        e.preventDefault();
        toggleTheme();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "chat" && messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, activeTab]);

  const handleSendQuery = async (queryText = null, explicitRoute = null) => {
    const rawQuery = (queryText || inputQuery).trim();
    if (!rawQuery || isLoading) return;

    setErrorBanner(null);
    setLastFailedQuery(null);
    setActiveTab("chat");
    if (explicitRoute) setSelectedRoute(explicitRoute);

    const pairIndex = Math.floor(messages.length / 2) + 1;
    const userMsgId = `usr_${Date.now()}`;
    const newUserMsg = {
      id: userMsgId,
      role: "user",
      content: rawQuery,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      pairIndex,
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setSelectedQuestionId(userMsgId);
    setHighlightedCitationIndex(null);
    setInputQuery("");
    setIsLoading(true);
    setActiveLiveStep("route");
    setLiveMessage("Classifying intent route...");

    const effectiveRoute = explicitRoute || selectedRoute;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const data = await streamAgentChat({
        url: `${API_BASE}/chat`,
        body: {
          query: rawQuery,
          thread_id: threadId,
          route: effectiveRoute,
        },
        signal: controller.signal,
        onEvent: ({ event, data: evtData }) => {
          if (event === "step" && evtData) {
            setActiveLiveStep(evtData.step || null);
            setLiveMessage(evtData.label || null);
          } else if (event === "reconnect" && evtData) {
            setLiveMessage(
              `Reconnecting stream (${evtData.attempt}/${evtData.maxRetries})...`
            );
          }
        },
      });

      if (data.thread_id) setThreadId(data.thread_id);

      const asstMsgId = `ast_${Date.now()}`;
      const newAssistantMsg = {
        id: asstMsgId,
        role: "assistant",
        content: data.answer || "No response generated.",
        tools_used: data.tools_used || [],
        sources: data.sources || [],
        trace: data.trace || null,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        pairIndex,
      };

      setMessages((prev) => [...prev, newAssistantMsg]);
      setActiveEvidence({
        query: rawQuery,
        answer: data.answer,
        tools_used: data.tools_used || [],
        sources: data.sources || [],
        trace: data.trace || {},
        messageIndex: pairIndex,
      });
      setIsEvidencePanelOpen(true);
      fetchConversations();
      fetchStatus();
    } catch (err) {
      if (err?.name !== "AbortError") {
        setLastFailedQuery(rawQuery);
        setErrorBanner(
          `Agent request failed: ${err.message}. Check backend connectivity at ${API_BASE}.`
        );
      }
    } finally {
      setIsLoading(false);
      setActiveLiveStep(null);
      setLiveMessage(null);
    }
  };

  const handleSelectEvidenceForPair = (pairIndex, citationIndex = null, openDrawer = true) => {
    const userMsg = messages.find((m) => m.role === "user" && m.pairIndex === pairIndex);
    const asstMsg = messages.find((m) => m.role === "assistant" && m.pairIndex === pairIndex);
    if (asstMsg) {
      setActiveEvidence({
        query: userMsg?.content || "Query",
        answer: asstMsg.content,
        tools_used: asstMsg.tools_used || [],
        sources: asstMsg.sources || [],
        trace: asstMsg.trace || {},
        messageIndex: pairIndex,
      });
      setHighlightedCitationIndex(citationIndex);
      if (openDrawer) setIsEvidencePanelOpen(true);
      if (userMsg) setSelectedQuestionId(userMsg.id);
    }
  };

  const handleSelectConversation = async (convId) => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/conversations/${convId}`);
      if (res.ok) {
        const data = await res.json();
        const convMsgs = (data.messages || []).map((m, idx) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          tools_used: safeJsonParse(m.tools_used, []),
          sources: safeJsonParse(m.sources, []),
          trace: safeJsonParse(m.trace, {}),
          timestamp: m.created_at
            ? new Date(m.created_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })
            : "",
          pairIndex: Math.floor(idx / 2) + 1,
        }));
        setMessages(convMsgs);
        setThreadId(convId);
        setActiveTab("chat");

        const lastAsst = convMsgs.filter((m) => m.role === "assistant").pop();
        if (lastAsst) {
          const prompt =
            convMsgs.find(
              (m) => m.role === "user" && m.pairIndex === lastAsst.pairIndex
            )?.content || "";
          setActiveEvidence({
            query: prompt,
            answer: lastAsst.content,
            tools_used: lastAsst.tools_used,
            sources: lastAsst.sources,
            trace: lastAsst.trace,
            messageIndex: lastAsst.pairIndex,
          });
          setIsEvidencePanelOpen(true);
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  const sessionHistory =
    conversations.length > 0
      ? conversations.map((c, idx) => ({
          id: c.id,
          tag: `Q_${String(idx + 1).padStart(2, "0")}`,
          query: c.initial_query || c.title || "Query",
          timestamp: c.updated_at
            ? new Date(c.updated_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })
            : "",
        }))
      : messages
          .filter((m) => m.role === "user")
          .map((m, idx) => ({
            id: m.id,
            tag: `Q_${String(idx + 1).padStart(2, "0")}`,
            query: m.content,
            timestamp: m.timestamp,
            pairIndex: m.pairIndex,
          }));

  const handleSelectHistoryItem = (historyId) => {
    const persisted = conversations.find((c) => c.id === historyId);
    if (persisted) {
      handleSelectConversation(historyId);
      return;
    }
    const userMsg = messages.find((m) => m.id === historyId);
    if (userMsg && userMsg.pairIndex) {
      handleSelectEvidenceForPair(userMsg.pairIndex);
      document
        .getElementById(userMsg.id)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div className="min-h-screen text-ink font-sans">
      {/* 1. Narrow Left Spine */}
      <Spine
        activeTab={activeTab}
        onSelectTab={switchTab}
        onNewSession={handleNewSession}
        history={sessionHistory}
        activeQuestionId={selectedQuestionId}
        onSelectHistory={handleSelectHistoryItem}
        systemHealth={systemHealth}
        pendingTicketsCount={pendingTicketsCount}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        onOpenKeyboardHelp={() => setIsKeyboardHelpOpen(true)}
      />

      {/* 2. Wide Main Column */}
      <div
        className={`min-h-screen flex flex-col md:pl-[188px] pb-14 md:pb-0 transition-[padding] duration-150 ${
          activeTab === "chat" && isEvidencePanelOpen ? "xl:pr-[392px]" : ""
        }`}
      >
        {/* Top Control Header */}
        <header className="sticky top-0 z-20 h-12 border-b border-grid bg-raised px-3 sm:px-6 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <button
              type="button"
              onClick={() => setIsMobileSidebarOpen(true)}
              className="md:hidden p-1.5 rounded-xs border border-grid bg-paper text-ink cursor-pointer"
              aria-label="Open navigation menu"
            >
              <Menu className="w-4 h-4" strokeWidth={1.6} />
            </button>

            {activeTab === "chat" && messages.length > 0 && (
              <button
                type="button"
                onClick={handleNewSession}
                aria-label="Overview"
                className="inline-flex items-center gap-1 px-2 py-1 rounded-xs border border-grid bg-paper text-ink hover:border-ink font-mono text-[11px] font-semibold cursor-pointer shrink-0"
              >
                <ArrowLeft className="w-3 h-3" strokeWidth={1.6} />
                <span className="hidden sm:inline">Overview</span>
              </button>
            )}

            <div className="flex items-center gap-1.5 font-mono text-xs min-w-0 truncate">
              <span className="text-muted hidden sm:inline uppercase tracking-wider text-[10.5px]">
                Fixdesk
              </span>
              <span className="text-muted hidden sm:inline">/</span>
              <span className="font-bold text-ink truncate">
                {activeTab === "chat" && "Analysis Logbook"}
                {activeTab === "support-desk" && "Support Desk"}
                {activeTab === "data-quality" && "Data Quality"}
                {activeTab === "documents" && "Documents Catalog"}
                {activeTab === "projects" && "Projects Registry"}
              </span>
              {activeTab === "chat" && (
                <span className="hidden md:inline px-1.5 py-0.2 rounded-xs border border-grid bg-sunken text-[10px] text-muted tabular-mono">
                  {threadId ? threadId.slice(0, 8).toUpperCase() : "SESSION"}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Live Agent Status Indicator */}
            <div
              role="status"
              aria-live="polite"
              className={`hidden sm:inline-flex items-center gap-1.5 px-2 py-1 rounded-xs border font-mono text-[10.5px] font-bold uppercase tracking-wider ${
                isLoading
                  ? "border-ink bg-highlighter text-highlighter-ink"
                  : "border-grid bg-sunken text-muted"
              }`}
            >
              <span
                className="w-2 h-2 rounded-xs"
                style={{
                  backgroundColor: isLoading ? "var(--ink)" : "var(--sage)",
                }}
              />
              <span>{isLoading ? liveMessage || "Working" : "Ready"}</span>
            </div>

            <button
              type="button"
              onClick={() => setIsCommandPaletteOpen(true)}
              className="md:hidden inline-flex items-center gap-1 px-2 py-1 rounded-xs border border-grid bg-paper text-ink font-mono text-[11px] cursor-pointer"
              aria-label="Open command palette"
            >
              <Search className="w-3.5 h-3.5" strokeWidth={1.6} />
            </button>

            <button
              type="button"
              onClick={() => setIsAddDataModalOpen(true)}
              aria-label="Add Data"
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs border border-grid bg-paper text-ink hover:border-ink font-mono text-[11px] font-semibold cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" strokeWidth={1.6} />
              <span className="hidden sm:inline">Add Data</span>
            </button>

            {activeTab === "chat" && (
              <button
                type="button"
                onClick={() => setIsEvidencePanelOpen((prev) => !prev)}
                aria-expanded={isEvidencePanelOpen}
                aria-label="Margin"
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs border font-mono text-[11px] font-bold cursor-pointer transition-colors ${
                  isEvidencePanelOpen
                    ? "border-ink bg-highlighter text-highlighter-ink"
                    : "border-grid bg-paper text-ink hover:border-ink"
                }`}
              >
                <PanelRight className="w-3.5 h-3.5" strokeWidth={1.6} />
                <span className="hidden sm:inline">Margin</span>
              </button>
            )}
          </div>
        </header>

        {/* Main Workspace Canvas */}
        <main className="flex-1 flex flex-col px-3 py-4 sm:px-6 lg:px-8 w-full min-w-0">
          {(systemHealth?.ai_budget?.warning_active || systemHealth?.ai_budget?.limit_reached) && (
            <div
              role="status"
              data-testid="ai-budget-banner"
              className={`mb-4 max-w-4xl mx-auto w-full px-3 py-2 rounded-xs border font-mono text-[11.5px] flex items-center justify-between gap-3 ${
                systemHealth.ai_budget.limit_reached
                  ? "border-seal bg-seal-tint text-seal-ink"
                  : "border-amber bg-amber-tint text-amber-ink"
              }`}
            >
              <span>
                <strong>
                  {systemHealth.ai_budget.limit_reached ? "AI BUDGET LIMIT REACHED" : "AI BUDGET WARNING"}:
                </strong>{" "}
                {systemHealth.ai_budget.message ||
                  `${systemHealth.ai_budget.requests_used}/${systemHealth.ai_budget.request_limit} requests, ${systemHealth.ai_budget.tokens_used}/${systemHealth.ai_budget.token_limit} tokens used today.`}
              </span>
              <span className="shrink-0 tabular-mono font-bold">
                {Math.round((systemHealth.ai_budget.usage_ratio || 0) * 100)}%
              </span>
            </div>
          )}

          {errorBanner && (
            <div className="mb-4 max-w-4xl mx-auto w-full">
              <ErrorState
                title="Execution Error"
                message={errorBanner}
                onRetry={
                  lastFailedQuery
                    ? () => handleSendQuery(lastFailedQuery)
                    : () => setErrorBanner(null)
                }
                retryLabel={lastFailedQuery ? "Retry Query" : "Dismiss"}
              />
            </div>
          )}

          {activeTab === "chat" && (
            <div className="w-full max-w-4xl mx-auto flex-1 flex flex-col justify-between min-w-0">
              <div className="flex-1 pb-6 space-y-2 min-w-0">
                {messages.length === 0 ? (
                  <EmptyState
                    onSelectQuery={(query, route) => handleSendQuery(query, route)}
                    systemHealth={systemHealth}
                    isStatusLoading={isStatusLoading}
                    statusError={statusError}
                    onRetryStatus={fetchStatus}
                    onDataRefresh={handleDataReload}
                  />
                ) : (
                  <>
                    <div className="flex items-center justify-between pb-2 border-b border-grid font-mono text-[11px] text-muted">
                      <span>
                        Log Entries ({Math.ceil(messages.length / 2)})
                      </span>
                      <button
                        type="button"
                        onClick={handleNewSession}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-xs border border-grid bg-raised text-ink hover:border-ink font-bold cursor-pointer"
                      >
                        <Plus className="w-3 h-3" strokeWidth={1.8} />
                        <span>New Query</span>
                      </button>
                    </div>

                    {messages.map((msg, idx) => {
                      const isSelected =
                        activeEvidence?.messageIndex === msg.pairIndex;
                      return (
                        <div key={msg.id} id={msg.id}>
                          <LogEntry
                            message={msg}
                            index={msg.pairIndex || idx + 1}
                            isSelected={isSelected}
                            highlightedCitationIndex={
                              isSelected ? highlightedCitationIndex : null
                            }
                            onSelectEvidence={() =>
                              handleSelectEvidenceForPair(msg.pairIndex, null, true)
                            }
                            onSelectCitation={(citIdx, opts = { openDrawer: true }) =>
                              handleSelectEvidenceForPair(
                                msg.pairIndex,
                                citIdx,
                                opts.openDrawer
                              )
                            }
                          />
                        </div>
                      );
                    })}
                  </>
                )}

                {isLoading && (
                  <div className="pt-2">
                    <Timeline
                      mode="horizontal"
                      isLoading={true}
                      activeLiveStep={activeLiveStep}
                      liveMessage={liveMessage}
                      toolsUsed={
                        selectedRoute === "data"
                          ? ["query_sales"]
                          : selectedRoute === "docs"
                          ? ["search_docs"]
                          : ["query_sales", "search_docs"]
                      }
                    />
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              <Composer
                inputQuery={inputQuery}
                onInputChange={setInputQuery}
                onSubmit={() => handleSendQuery()}
                isLoading={isLoading}
                selectedRoute={selectedRoute}
                onRouteChange={setSelectedRoute}
                composerRef={composerInputRef}
              />
            </div>
          )}

          {activeTab === "support-desk" && (
            <SupportDeskView
              onUpdatePendingCount={setPendingTicketsCount}
              externalTicketId={externalTicketId}
              onClearExternalTicket={() => setExternalTicketId(null)}
            />
          )}

          {activeTab === "data-quality" && (
            <DataQualityView
              report={dataQualityReport}
              isLoading={isDataQualityLoading}
              error={dataQualityError}
              onRefresh={fetchDataQuality}
              systemHealth={systemHealth}
            />
          )}

          {activeTab === "documents" && (
            <DocumentsView
              documents={indexedSources}
              systemHealth={systemHealth}
              onRefresh={fetchSources}
              isLoading={isSourcesLoading}
              error={sourcesError}
              onSelectDocPrompt={(prompt) => {
                setActiveTab("chat");
                handleSendQuery(prompt, "docs");
              }}
              externalDocFile={externalDocFile}
              onClearExternalDoc={() => setExternalDocFile(null)}
            />
          )}

          {activeTab === "projects" && <ProjectsView />}
        </main>
      </div>

      {/* 3. Right Margin Notes Column (Desktop xl+ OR Mobile Bottom Sheet) */}
      {activeTab === "chat" && isEvidencePanelOpen && isDesktopXl && (
        <div className="fixed top-0 right-0 bottom-0 w-[392px] z-30 border-l border-grid bg-raised">
          <Margin
            activeEvidence={activeEvidence}
            highlightedCitationIndex={highlightedCitationIndex}
            onClose={() => setIsEvidencePanelOpen(false)}
            isLoading={isLoading}
            activeLiveStep={activeLiveStep}
            liveMessage={liveMessage}
          />
        </div>
      )}

      {activeTab === "chat" && isEvidencePanelOpen && !isDesktopXl && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-stretch sm:justify-end bg-ink/45"
          role="dialog"
          aria-modal="true"
          aria-label="Evidence margin sheet"
          onClick={() => setIsEvidencePanelOpen(false)}
        >
          <div
            className="w-full sm:max-w-md h-[84vh] sm:h-full bg-raised border-t sm:border-t-0 sm:border-s border-grid rounded-t-xs sm:rounded-none overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <Margin
              activeEvidence={activeEvidence}
              highlightedCitationIndex={highlightedCitationIndex}
              onClose={() => setIsEvidencePanelOpen(false)}
              isLoading={isLoading}
              activeLiveStep={activeLiveStep}
              liveMessage={liveMessage}
            />
          </div>
        </div>
      )}

      {/* Modals & Palettes */}
      <AddDataModal
        isOpen={isAddDataModalOpen}
        onClose={() => setIsAddDataModalOpen(false)}
        onPipelineComplete={handleDataReload}
      />

      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectTab={switchTab}
        onNewSession={handleNewSession}
        onOpenAddData={() => setIsAddDataModalOpen(true)}
        onToggleEvidence={() => setIsEvidencePanelOpen((prev) => !prev)}
        onToggleTheme={toggleTheme}
        onOpenHelp={() => setIsKeyboardHelpOpen(true)}
        onDispatchQuery={(q) => handleSendQuery(q)}
        tickets={supportTickets}
        documents={indexedSources}
        onOpenTicket={(ticketId) => {
          switchTab("support-desk");
          setExternalTicketId(ticketId);
        }}
        onOpenDocument={(sourceFile) => {
          switchTab("documents");
          setExternalDocFile(sourceFile);
        }}
      />

      <KeyboardHelpModal
        isOpen={isKeyboardHelpOpen}
        onClose={() => setIsKeyboardHelpOpen(false)}
      />
    </div>
  );
}
