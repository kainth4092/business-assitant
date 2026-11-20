"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Menu,
  Layers,
  ArrowUp,
  AlertCircle,
  Database,
  BarChart3,
  BookOpen,
  MessageSquare,
  RefreshCw,
  X,
  Compass,
  FileText,
  Terminal,
  RotateCw
} from "lucide-react";

import Sidebar from "../components/Sidebar";
import ChatMessage from "../components/ChatMessage";
import EvidencePanel from "../components/EvidencePanel";
import EmptyState from "../components/EmptyState";
import Composer from "../components/Composer";
import Timeline from "../components/Timeline";
import ThemeToggle from "../components/ThemeToggle";
import DataQualityView from "../components/DataQualityView";
import DocumentsView from "../components/DocumentsView";
import SupportDeskView from "../components/SupportDeskView";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AnalystWorkbenchPage() {
  // Navigation & view states
  const [activeTab, setActiveTab] = useState("chat"); // 'chat' | 'data-quality' | 'documents' | 'support-desk'
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isEvidencePanelOpen, setIsEvidencePanelOpen] = useState(false);

  // Composer states
  const [selectedRoute, setSelectedRoute] = useState("auto");
  const [inputQuery, setInputQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState(null);

  // Conversation & Agent states
  const [messages, setMessages] = useState([]);
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState(null);

  // Backend data states
  const [systemHealth, setSystemHealth] = useState(null);
  const [dataQualityReport, setDataQualityReport] = useState(null);
  const [indexedSources, setIndexedSources] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [pendingTicketsCount, setPendingTicketsCount] = useState(0);
  const [isDataQualityLoading, setIsDataQualityLoading] = useState(false);
  const [isSourcesLoading, setIsSourcesLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);

  // References
  const messagesEndRef = useRef(null);

  // Initial load: Fetch status, data quality, indexed sources, support tickets count, conversations
  useEffect(() => {
    fetchStatus();
    fetchDataQuality();
    fetchSources();
    fetchConversations();
    fetchPendingTicketsCount();

    if (typeof window !== "undefined" && window.innerWidth >= 1280) {
      setIsEvidencePanelOpen(true);
    }
  }, []);

  // Keyboard shortcut: Escape closes drawers
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        setIsMobileSidebarOpen(false);
        if (window.innerWidth < 1280) {
          setIsEvidencePanelOpen(false);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Scroll to bottom when new messages arrive or loading begins
  useEffect(() => {
    if (activeTab === "chat" && messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, activeTab]);

  // API Call: /status
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (res.ok) {
        const data = await res.json();
        setSystemHealth(data);
      }
    } catch (e) {
      console.warn("Backend not reachable yet", e);
    }
  };

  // API Call: /conversations
  const fetchConversations = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
      }
    } catch (e) {
      console.warn("Could not fetch conversations", e);
    }
  };

  // API Call: /data-quality
  const fetchDataQuality = async () => {
    setIsDataQualityLoading(true);
    try {
      const res = await fetch(`${API_BASE}/data-quality`);
      if (res.ok) {
        const data = await res.json();
        setDataQualityReport(data);
      }
    } catch (e) {
      console.warn("Could not fetch data quality", e);
    } finally {
      setIsDataQualityLoading(false);
    }
  };

  // API Call: /sources
  const fetchSources = async () => {
    setIsSourcesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sources`);
      if (res.ok) {
        const data = await res.json();
        setIndexedSources(data.documents || []);
      }
    } catch (e) {
      console.warn("Could not fetch sources", e);
    } finally {
      setIsSourcesLoading(false);
    }
  };

  // API Call: /support/tickets count
  const fetchPendingTicketsCount = async () => {
    try {
      const res = await fetch(`${API_BASE}/support/tickets`);
      if (res.ok) {
        const data = await res.json();
        const list = data.tickets || [];
        const pending = list.filter((t) => t.status === "fix_ready").length;
        setPendingTicketsCount(pending);
      }
    } catch (e) {
      console.warn("Could not fetch support tickets count", e);
    }
  };

  // Reset conversation to clean state
  const handleNewSession = () => {
    setMessages([]);
    setActiveEvidence(null);
    setSelectedQuestionId(null);
    setThreadId(null);
    setInputQuery("");
    setErrorBanner(null);
    setActiveTab("chat");
    setSelectedRoute("auto");
    if (window.innerWidth < 1280) {
      setIsEvidencePanelOpen(false);
    }
  };

  // Submit query to LangGraph agent
  const handleSendQuery = async (queryText = null, explicitRoute = null) => {
    const rawQuery = (queryText || inputQuery).trim();
    if (!rawQuery || isLoading) return;

    setErrorBanner(null);
    setActiveTab("chat");

    if (explicitRoute) {
      setSelectedRoute(explicitRoute);
    }

    const pairIndex = Math.floor(messages.length / 2) + 1;
    const userMsgId = `usr_${Date.now()}`;
    const newUserMsg = {
      id: userMsgId,
      role: "user",
      content: rawQuery,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      pairIndex
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setSelectedQuestionId(userMsgId);
    setInputQuery("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: rawQuery,
          thread_id: threadId
        })
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => null);
        throw new Error(errJson?.detail || `Server returned HTTP status ${response.status}`);
      }

      const data = await response.json();
      if (data.thread_id) {
        setThreadId(data.thread_id);
      }

      const asstMsgId = `ast_${Date.now()}`;
      const newAssistantMsg = {
        id: asstMsgId,
        role: "assistant",
        content: data.answer || "No response generated.",
        tools_used: data.tools_used || [],
        sources: data.sources || [],
        trace: data.trace || null,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        pairIndex
      };

      setMessages((prev) => [...prev, newAssistantMsg]);

      // Automatically populate and reveal evidence in right panel
      const evidencePayload = {
        query: rawQuery,
        answer: data.answer,
        tools_used: data.tools_used || [],
        sources: data.sources || [],
        trace: data.trace || {},
        messageIndex: pairIndex
      };
      setActiveEvidence(evidencePayload);
      setIsEvidencePanelOpen(true);
      fetchConversations();
      fetchStatus();
    } catch (err) {
      console.error("Agent query failed:", err);
      setErrorBanner(
        `Failed to complete agent execution: ${err.message}. Ensure backend is running at ${API_BASE}.`
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Inspect evidence for a specific message pair
  const handleSelectEvidenceForPair = (pairIndex) => {
    const userMsg = messages.find((m) => m.role === "user" && m.pairIndex === pairIndex);
    const asstMsg = messages.find((m) => m.role === "assistant" && m.pairIndex === pairIndex);

    if (asstMsg) {
      setActiveEvidence({
        query: userMsg?.content || "User Query",
        answer: asstMsg.content,
        tools_used: asstMsg.tools_used || [],
        sources: asstMsg.sources || [],
        trace: asstMsg.trace || {},
        messageIndex: pairIndex
      });
      setIsEvidencePanelOpen(true);
      if (userMsg) {
        setSelectedQuestionId(userMsg.id);
      }
    }
  };

  // Select a historical conversation loaded from PostgreSQL
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
          tools_used: typeof m.tools_used === "string" ? JSON.parse(m.tools_used) : m.tools_used || [],
          sources: typeof m.sources === "string" ? JSON.parse(m.sources) : m.sources || [],
          trace: typeof m.trace === "string" ? JSON.parse(m.trace) : m.trace || {},
          timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "",
          pairIndex: Math.floor(idx / 2) + 1
        }));
        setMessages(convMsgs);
        setThreadId(convId);
        setActiveTab("chat");
        
        const lastAsst = convMsgs.filter((m) => m.role === "assistant").pop();
        if (lastAsst) {
          const userPrompt = convMsgs.find((m) => m.role === "user" && m.pairIndex === lastAsst.pairIndex)?.content || "";
          setActiveEvidence({
            query: userPrompt,
            answer: lastAsst.content,
            tools_used: lastAsst.tools_used,
            sources: lastAsst.sources,
            trace: lastAsst.trace,
            messageIndex: lastAsst.pairIndex
          });
          setIsEvidencePanelOpen(true);
        }
      }
    } catch (err) {
      console.error("Failed to load conversation:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Prepare session history items for sidebar (from PostgreSQL conversations or current session)
  const sessionHistory = conversations.length > 0
    ? conversations.map((c, idx) => ({
        id: c.id,
        tag: `Q_${String(idx + 1).padStart(2, "0")}`,
        query: c.initial_query || c.title || "User Query",
        timestamp: c.updated_at ? new Date(c.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "",
        isPersisted: true
      }))
    : messages
        .filter((m) => m.role === "user")
        .map((m, idx) => ({
          id: m.id,
          tag: `Q_${String(idx + 1).padStart(2, "0")}`,
          query: m.content,
          timestamp: m.timestamp,
          pairIndex: m.pairIndex
        }));

  const handleSelectHistoryItem = (historyId) => {
    const isPersisted = conversations.find((c) => c.id === historyId);
    if (isPersisted) {
      handleSelectConversation(historyId);
      return;
    }
    const userMsg = messages.find((m) => m.id === historyId);
    if (userMsg && userMsg.pairIndex) {
      handleSelectEvidenceForPair(userMsg.pairIndex);
      const el = document.getElementById(userMsg.id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };

  return (
    <div className="min-h-screen bg-page text-primary font-body antialiased selection:bg-accent-lime/20 selection:text-primary transition-colors">
      {/* ---------------------------------------------------------------------- */}
      {/* 1. LEFT UTILITY RAIL (72px desktop / mobile drawer)                    */}
      {/* ---------------------------------------------------------------------- */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={(tab) => {
          setActiveTab(tab);
          if (tab !== "chat" && window.innerWidth < 1280) {
            setIsEvidencePanelOpen(false);
          }
          if (tab === "support-desk") {
            fetchPendingTicketsCount();
          }
        }}
        onNewSession={handleNewSession}
        history={sessionHistory}
        activeQuestionId={selectedQuestionId}
        onSelectHistory={handleSelectHistoryItem}
        systemHealth={systemHealth}
        pendingTicketsCount={pendingTicketsCount}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* ---------------------------------------------------------------------- */}
      {/* 2. MAIN COLUMN (Offset by 72px sidebar, adjusts for 420px evidence)   */}
      {/* ---------------------------------------------------------------------- */}
      <div
        className={`min-h-screen flex flex-col transition-[margin] duration-normal lg:ml-[72px] ${
          isEvidencePanelOpen ? "xl:mr-[420px]" : "mr-0"
        }`}
      >
        {/* Sticky Top Header (Matches Stitch Spec) */}
        <header
          className="sticky top-0 z-30 h-14 border-b border-border px-4 sm:px-6 flex items-center justify-between shadow-xs transition-colors"
          style={{ backgroundColor: "var(--bg-surface)" }}
        >
          <div className="flex items-center gap-3">
            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setIsMobileSidebarOpen(true)}
              className="p-1.5 rounded-md border border-border hover:bg-surface-high text-muted hover:text-primary lg:hidden transition-colors"
              aria-label="Open navigation sidebar"
            >
              <Menu className="w-4 h-4 stroke-[2]" />
            </button>

            {/* Breadcrumb Hierarchy */}
            <div className="flex items-center gap-2 font-mono text-label-telemetry">
              <span className="text-muted uppercase tracking-wider font-bold hidden sm:inline">
                BUSINESS ASSISTANT
              </span>
              <span className="text-muted hidden sm:inline">&rsaquo;</span>
              <span className="text-primary font-bold text-code-md">
                {activeTab === "chat" && "Live Analysis & Log"}
                {activeTab === "support-desk" && "Support Desk & Autonomous Remediation"}
                {activeTab === "data-quality" && "PySpark Data Quality Telemetry"}
                {activeTab === "documents" && "Document Knowledge Repository"}
              </span>
              <span className="hidden md:inline px-1.5 py-0.5 rounded bg-surface-container font-mono text-[10px] text-muted border border-border">
                #{threadId ? threadId.slice(0, 8).toUpperCase() : "LIVE"}
              </span>
            </div>
          </div>

          {/* Right Header Affordances */}
          <div className="flex items-center gap-2.5">
            {/* Live Agent Working / Ready Status Pill */}
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded bg-surface-container border border-border">
              <span className="relative flex h-2 w-2">
                {isLoading ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-lime opacity-80" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-lime" />
                  </>
                ) : (
                  <span className="w-2 h-2 rounded-full bg-accent-emerald" />
                )}
              </span>
              <span
                className={`font-mono text-label-telemetry uppercase font-bold tracking-wider ${
                  isLoading ? "text-accent-lime" : "text-muted"
                }`}
              >
                {isLoading ? "AGENT WORKING" : "AGENT READY"}
              </span>
            </div>

            {/* Toggle Evidence Panel Button */}
            {activeTab === "chat" && (
              <button
                onClick={() => setIsEvidencePanelOpen(!isEvidencePanelOpen)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-md border transition-all ${
                  isEvidencePanelOpen
                    ? "bg-accent-lime text-accent-lime-contrast border-accent-lime shadow-xs"
                    : "border-border bg-surface text-primary hover:bg-surface-high"
                }`}
                title="Toggle Live Evidence & Telemetry Panel"
              >
                <Layers className="w-3.5 h-3.5 stroke-[2]" />
                <span className="hidden sm:inline">Evidence</span>
                {activeEvidence && (
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-lime animate-pulse" />
                )}
              </button>
            )}

            {/* Refresh Action for other views */}
            {activeTab === "data-quality" && (
              <button
                onClick={fetchDataQuality}
                disabled={isDataQualityLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-md border border-border bg-surface text-primary hover:bg-surface-high transition-all"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 stroke-[2] ${isDataQualityLoading ? "animate-spin" : ""}`}
                />
                <span className="hidden sm:inline">Refresh</span>
              </button>
            )}

            {activeTab === "documents" && (
              <button
                onClick={fetchSources}
                disabled={isSourcesLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-md border border-border bg-surface text-primary hover:bg-surface-high transition-all"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 stroke-[2] ${isSourcesLoading ? "animate-spin" : ""}`}
                />
                <span className="hidden sm:inline">Refresh</span>
              </button>
            )}

            {/* Dark/Light Theme Toggle */}
            <ThemeToggle />
          </div>
        </header>

        {/* Global Error Banner */}
        {errorBanner && (
          <div className="px-4 py-3 bg-accent-crimson/15 border-b border-accent-crimson/30 text-accent-crimson text-xs flex items-center justify-between font-medium">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 stroke-[2.2]" />
              <span>{errorBanner}</span>
            </div>
            <button
              onClick={() => setErrorBanner(null)}
              className="text-accent-crimson hover:underline font-mono text-[11px] ml-4 font-bold"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Main Workspace Area */}
        <main className="flex-1 flex flex-col px-4 py-3 sm:px-6 sm:py-4 lg:px-8 lg:py-4 w-full">
          {/* TAB 1: Live Chat / Analysis Log */}
          {activeTab === "chat" && (
            <div className="w-full max-w-4xl xl:max-w-5xl mx-auto flex-1 flex flex-col justify-between">
              {/* Message Log or Empty State */}
              <div className="flex-1 pb-36 space-y-3">
                {messages.length === 0 ? (
                  <EmptyState
                    onSelectQuery={(query, route) => handleSendQuery(query, route)}
                    systemHealth={systemHealth}
                  />
                ) : (
                  messages.map((msg, index) => {
                    const isSelected =
                      activeEvidence &&
                      activeEvidence.messageIndex === msg.pairIndex;

                    return (
                      <div key={msg.id} id={msg.id}>
                        <ChatMessage
                          message={msg}
                          index={msg.pairIndex || index + 1}
                          isSelected={isSelected}
                          onSelectEvidence={() =>
                            handleSelectEvidenceForPair(msg.pairIndex)
                          }
                        />
                      </div>
                    );
                  })
                )}

                {/* Horizontal Pipeline Tracker during active agent execution */}
                {isLoading && (
                  <div className="pt-2 animate-fade-up">
                    <Timeline
                      mode="horizontal"
                      isLoading={true}
                      toolsUsed={selectedRoute === "data" ? ["query_sales"] : selectedRoute === "docs" ? ["search_docs"] : ["query_sales", "search_docs"]}
                    />
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Raised Composer Card */}
              <Composer
                inputQuery={inputQuery}
                onInputChange={(val) => setInputQuery(val)}
                onSubmit={() => handleSendQuery()}
                isLoading={isLoading}
                selectedRoute={selectedRoute}
                onRouteChange={(route) => setSelectedRoute(route)}
              />
            </div>
          )}

          {/* TAB 2: Data Quality Report */}
          {activeTab === "data-quality" && (
            <DataQualityView
              report={dataQualityReport}
              isLoading={isDataQualityLoading}
              onRefresh={fetchDataQuality}
              systemHealth={systemHealth}
            />
          )}

          {/* TAB 3: Documents Repository */}
          {activeTab === "documents" && (
            <DocumentsView
              documents={indexedSources}
              systemHealth={systemHealth}
              onRefresh={fetchSources}
              isLoading={isSourcesLoading}
              onSelectDocPrompt={(prompt) => {
                setActiveTab("chat");
                handleSendQuery(prompt);
              }}
            />
          )}

          {/* TAB 4: Support Desk & Remediation */}
          {activeTab === "support-desk" && (
            <SupportDeskView onUpdatePendingCount={fetchPendingTicketsCount} />
          )}
        </main>
      </div>

      {/* ---------------------------------------------------------------------- */}
      {/* 3. RIGHT EVIDENCE & AUDIT PANEL (420px Desktop / Mobile Bottom Sheet) */}
      {/* ---------------------------------------------------------------------- */}
      {/* Desktop Fixed Panel */}
      <div
        className={`hidden xl:block fixed top-0 right-0 bottom-0 w-[420px] bg-surface-lowest z-30 border-l border-border transition-transform duration-normal ease-in-out ${
          isEvidencePanelOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <EvidencePanel
          activeEvidence={activeEvidence}
          onClose={() => setIsEvidencePanelOpen(false)}
        />
      </div>

      {/* Mobile Bottom Sheet & Tablet Drawer for Evidence Panel */}
      {isEvidencePanelOpen && (
        <div className="xl:hidden fixed inset-0 z-50 flex items-end sm:items-stretch sm:justify-end">
          {/* Backdrop */}
          <div
            onClick={() => setIsEvidencePanelOpen(false)}
            className="fixed inset-0 bg-black/50 transition-opacity backdrop-blur-xs xl:hidden"
            aria-hidden="true"
          />

          {/* Panel Container */}
          <div className="relative w-full sm:max-w-md bg-surface h-[85vh] sm:h-full border-t sm:border-t-0 sm:border-l border-border shadow-2xl z-50 rounded-t-xl sm:rounded-none overflow-hidden flex flex-col">
            <div className="sm:hidden w-12 h-1.5 bg-border rounded-full mx-auto my-2.5 shrink-0" />
            <div className="flex-1 overflow-hidden">
              <EvidencePanel
                activeEvidence={activeEvidence}
                onClose={() => setIsEvidencePanelOpen(false)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
