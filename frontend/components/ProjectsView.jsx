"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  FolderGit2,
  RefreshCw,
  Send,
  ShieldAlert,
  FileCode2,
  GitBranch,
  GitCommit,
  ChevronRight,
  Search,
} from "lucide-react";
import Stamp from "./Stamp";
import Skeleton from "./Skeleton";
import ErrorState from "./ErrorState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ProjectsView() {
  const [projects, setProjects] = useState([]);
  const [selectedName, setSelectedName] = useState(null);
  const [indexStatus, setIndexStatus] = useState(null);
  const [fileTree, setFileTree] = useState([]);
  const [skippedFiles, setSkippedFiles] = useState([]);
  const [dbError, setDbError] = useState(null);

  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [projectsError, setProjectsError] = useState(null);

  const [isIndexing, setIsIndexing] = useState(false);
  const [indexFeedback, setIndexFeedback] = useState(null);
  const [indexError, setIndexError] = useState(null);

  const [question, setQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [askError, setAskError] = useState(null);
  const [askResult, setAskResult] = useState(null);
  const [activeChunkIndex, setActiveChunkIndex] = useState(0);

  const [detailSubtab, setDetailSubtab] = useState("ask"); // "ask" | "skipped" | "tree"

  const fetchProjectDetails = useCallback(async (projectName) => {
    if (!projectName) return;
    setIsLoadingDetails(true);
    try {
      const [statusRes, skippedRes] = await Promise.all([
        fetch(`${API_BASE}/projects/${encodeURIComponent(projectName)}/index-status`),
        fetch(`${API_BASE}/projects/${encodeURIComponent(projectName)}/skipped`),
      ]);
      if (statusRes.ok) {
        const stData = await statusRes.json();
        setIndexStatus(stData.project || null);
        setFileTree(stData.file_tree || []);
      } else {
        setIndexStatus(null);
        setFileTree([]);
      }
      if (skippedRes.ok) {
        const skData = await skippedRes.json();
        setSkippedFiles(skData.skipped_files || []);
      } else {
        setSkippedFiles([]);
      }
    } catch {
      setIndexStatus(null);
      setFileTree([]);
      setSkippedFiles([]);
    } finally {
      setIsLoadingDetails(false);
    }
  }, []);

  const fetchProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    setProjectsError(null);
    try {
      const res = await fetch(`${API_BASE}/projects`);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      const list = data.projects || [];
      setProjects(list);
      setDbError(data.database_ready === false ? data.database_error || "Database disconnected." : null);
      const target =
        selectedName && list.some((p) => p.name === selectedName)
          ? selectedName
          : list[0]?.name || null;
      setSelectedName(target);
      if (target) {
        await fetchProjectDetails(target);
      }
    } catch (err) {
      setProjectsError(err.message || "Could not load registered projects.");
    } finally {
      setIsLoadingProjects(false);
    }
  }, [fetchProjectDetails, selectedName]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/projects`);
        if (!active) return;
        if (!res.ok) {
          const err = await res.json().catch(() => null);
          throw new Error(err?.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        const list = data.projects || [];
        if (!active) return;
        setProjects(list);
        setDbError(data.database_ready === false ? data.database_error || "Database disconnected." : null);
        const initialName = list[0]?.name || null;
        setSelectedName(initialName);
        if (initialName) {
          await fetchProjectDetails(initialName);
        }
      } catch (err) {
        if (active) {
          setProjectsError(err.message || "Could not load registered projects.");
        }
      } finally {
        if (active) setIsLoadingProjects(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [fetchProjectDetails]);

  const handleSelectProject = async (name) => {
    setSelectedName(name);
    setAskResult(null);
    setAskError(null);
    setIndexFeedback(null);
    setIndexError(null);
    await fetchProjectDetails(name);
  };

  const handleTriggerIndex = async (incremental = true) => {
    if (!selectedName || isIndexing) return;
    setIsIndexing(true);
    setIndexError(null);
    setIndexFeedback(null);
    try {
      const res = await fetch(
        `${API_BASE}/projects/${encodeURIComponent(selectedName)}/index`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ incremental }),
        }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setIndexFeedback(
        `Indexed ${data.indexed_files} updated files (${data.unchanged_files} unchanged, ${data.removed_files} removed, ${data.indexed_chunks} new chunks, ${data.skipped_count} skipped).`
      );
      await fetchProjects();
    } catch (err) {
      setIndexError(err.message || "Project indexing failed.");
    } finally {
      setIsIndexing(false);
    }
  };

  const handleAsk = async (e) => {
    e?.preventDefault();
    const trimmed = question.trim();
    if (!selectedName || !trimmed || isAsking) return;
    setIsAsking(true);
    setAskError(null);
    setAskResult(null);
    setActiveChunkIndex(0);
    try {
      const res = await fetch(
        `${API_BASE}/projects/${encodeURIComponent(selectedName)}/ask`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmed, top_k: 6 }),
        }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setAskResult(data);
    } catch (err) {
      setAskError(err.message || "Codebase query failed.");
    } finally {
      setIsAsking(false);
    }
  };

  const activeProject =
    projects.find((p) => p.name === selectedName) || indexStatus || null;
  const activeChunks = askResult?.chunks || [];
  const focusedChunk = activeChunks[activeChunkIndex] || null;

  return (
    <div className="h-full overflow-y-auto px-4 md:px-7 py-5 pb-24 md:pb-8">
      <div className="max-w-6xl mx-auto space-y-5">
        {/* Top Section Strip Header */}
        <header className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-grid">
          <div className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-xs border border-grid bg-raised flex items-center justify-center text-ink">
              <FolderGit2 className="w-4 h-4" strokeWidth={1.6} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-serif text-xl font-bold text-ink tracking-tight">
                  Codebase Index Registry
                </h1>
                <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded-xs border border-grid bg-sunken text-muted">
                  code_rag
                </span>
              </div>
              <p className="font-sans text-xs text-muted mt-0.5">
                Project-aware AST + pgvector RAG with mandatory secret exclusion and file:line citations
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchProjects}
              disabled={isLoadingProjects}
              className="px-2.5 py-1.5 rounded-xs border border-grid bg-raised text-ink hover:bg-sunken font-mono text-[11px] flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${isLoadingProjects ? "animate-spin" : ""}`}
                strokeWidth={1.6}
              />
              <span>Refresh</span>
            </button>

            <button
              type="button"
              onClick={() => handleTriggerIndex(true)}
              disabled={!selectedName || isIndexing}
              className="px-3 py-1.5 rounded-xs border border-ink bg-ink text-paper hover:opacity-90 font-mono text-[11px] font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${isIndexing ? "animate-spin" : ""}`}
                strokeWidth={1.7}
              />
              <span>{isIndexing ? "Indexing..." : "Re-Index Incremental"}</span>
            </button>

            <button
              type="button"
              onClick={() => handleTriggerIndex(false)}
              disabled={!selectedName || isIndexing}
              className="px-2.5 py-1.5 rounded-xs border border-grid bg-raised text-ink hover:bg-sunken font-mono text-[11px] cursor-pointer disabled:opacity-50"
            >
              Full Rebuild
            </button>
          </div>
        </header>

        {/* Honest Database / Error Alerts */}
        {projectsError && (
          <ErrorState
            title="Could not load Projects API"
            message={projectsError}
            onRetry={fetchProjects}
          />
        )}

        {dbError && !projectsError && (
          <div className="px-3.5 py-2.5 rounded-xs border border-amber bg-amber-tint text-xs text-ink font-sans flex items-center justify-between gap-3">
            <span>
              <strong className="font-mono uppercase text-[10px] mr-2">
                Store Offline
              </strong>
              PostgreSQL `code_rag` store unreachable ({dbError}). Run Docker Postgres or CLI indexing once database is active.
            </span>
          </div>
        )}

        {indexError && (
          <div className="px-3.5 py-2.5 rounded-xs border border-seal bg-seal-tint text-xs text-seal-ink font-sans">
            <strong className="font-mono uppercase text-[10px] mr-2">
              Index Error
            </strong>
            {indexError}
          </div>
        )}

        {indexFeedback && (
          <div className="px-3.5 py-2.5 rounded-xs border border-sage bg-sage-tint text-xs text-sage-ink font-mono">
            {indexFeedback}
          </div>
        )}

        {/* Loading State */}
        {isLoadingProjects ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton lines={4} />
            <Skeleton lines={4} />
          </div>
        ) : projects.length === 0 ? (
          <div className="p-8 rounded-xs border border-grid bg-raised paper-stack text-center">
            <p className="font-serif text-base font-semibold text-ink">
              No projects registered
            </p>
            <p className="font-sans text-xs text-muted mt-1 max-w-md mx-auto">
              Add target repositories to <code className="font-mono">projects.yaml</code> and click Re-Index or run{" "}
              <code className="font-mono">project-init index &lt;name&gt;</code>.
            </p>
          </div>
        ) : (
          <>
            {/* Registered Project Flight Strips */}
            <section aria-label="Registered repositories" className="space-y-2.5">
              {projects.map((proj) => {
                const isSelected = proj.name === selectedName;
                const statusVariant =
                  proj.status === "indexed"
                    ? "pass"
                    : proj.status === "indexing"
                    ? "investigating"
                    : proj.status === "error" || proj.status === "database_unavailable"
                    ? "flagged"
                    : "new";
                const statusLabel =
                  proj.status === "indexed"
                    ? "INDEXED"
                    : proj.status === "database_unavailable"
                    ? "DB OFFLINE"
                    : (proj.status || "NOT INDEXED").toUpperCase().replace(/_/g, " ");

                return (
                  <button
                    key={proj.name}
                    type="button"
                    onClick={() => handleSelectProject(proj.name)}
                    className={`w-full text-left p-3.5 rounded-xs border transition-colors cursor-pointer paper-stack flex flex-wrap items-center justify-between gap-4 ${
                      isSelected
                        ? "border-ink bg-raised ring-1 ring-ink/20"
                        : "border-grid bg-raised hover:bg-sunken/70"
                    }`}
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span
                          className={`font-serif text-base font-bold text-ink ${
                            isSelected ? "bg-highlighter-wash px-1 -mx-1" : ""
                          }`}
                        >
                          {proj.name}
                        </span>
                        <span className="font-mono text-[10px] text-muted flex items-center gap-1">
                          <GitBranch className="w-3 h-3" strokeWidth={1.6} />
                          {proj.default_branch}
                        </span>
                        <span className="font-mono text-[10px] text-muted flex items-center gap-1">
                          <GitCommit className="w-3 h-3" strokeWidth={1.6} />
                          {proj.last_commit_hash ? proj.last_commit_hash.slice(0, 10) : "uncommitted"}
                        </span>
                      </div>
                      <div className="font-mono text-[11px] text-muted truncate">
                        {proj.local_path}
                      </div>
                    </div>

                    <div className="flex items-center gap-5 shrink-0">
                      <div className="text-right">
                        <div className="font-mono text-[9.5px] uppercase text-muted">Files</div>
                        <div className="font-mono text-sm font-bold tabular-mono text-ink">
                          {proj.file_count}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-[9.5px] uppercase text-muted">Chunks</div>
                        <div className="font-mono text-sm font-bold tabular-mono text-ink">
                          {proj.chunk_count}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-[9.5px] uppercase text-muted">Skipped</div>
                        <div className="font-mono text-sm font-bold tabular-mono text-seal-ink">
                          {proj.skipped_count}
                        </div>
                      </div>
                      <Stamp variant={statusVariant} label={statusLabel} size="sm" />
                    </div>
                  </button>
                );
              })}
            </section>

            {/* Sub-Navigation Tabs inside Active Project */}
            {activeProject && (
              <div className="rounded-xs border border-grid bg-raised paper-stack overflow-hidden">
                <div className="px-4 py-2.5 bg-sunken border-b border-grid flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5" role="tablist" aria-label="Project inspection views">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={detailSubtab === "ask"}
                      onClick={() => setDetailSubtab("ask")}
                      className={`px-2.5 py-1 rounded-xs font-mono text-[11px] border cursor-pointer ${
                        detailSubtab === "ask"
                          ? "border-ink bg-highlighter-wash text-ink font-bold"
                          : "border-grid bg-raised text-muted hover:text-ink"
                      }`}
                    >
                      Ask Codebase
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={detailSubtab === "skipped"}
                      onClick={() => setDetailSubtab("skipped")}
                      className={`px-2.5 py-1 rounded-xs font-mono text-[11px] border cursor-pointer ${
                        detailSubtab === "skipped"
                          ? "border-ink bg-highlighter-wash text-ink font-bold"
                          : "border-grid bg-raised text-muted hover:text-ink"
                      }`}
                    >
                      Skipped Files ({skippedFiles.length})
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={detailSubtab === "tree"}
                      onClick={() => setDetailSubtab("tree")}
                      className={`px-2.5 py-1 rounded-xs font-mono text-[11px] border cursor-pointer ${
                        detailSubtab === "tree"
                          ? "border-ink bg-highlighter-wash text-ink font-bold"
                          : "border-grid bg-raised text-muted hover:text-ink"
                      }`}
                    >
                      Indexed Tree ({fileTree.length})
                    </button>
                  </div>

                  <div className="font-mono text-[10px] text-muted">
                    {activeProject.last_indexed_at
                      ? `Last indexed: ${activeProject.last_indexed_at}`
                      : "Not indexed yet"}
                  </div>
                </div>

                {/* TAB 1: ASK CODEBASE + CITATIONS */}
                {detailSubtab === "ask" && (
                  <div className="p-4 space-y-4">
                    <form onSubmit={handleAsk} className="flex flex-col sm:flex-row gap-2">
                      <label htmlFor="codebase-question-input" className="sr-only">
                        Ask a question about {activeProject.name}
                      </label>
                      <div className="relative flex-1">
                        <Search
                          className="w-3.5 h-3.5 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                          strokeWidth={1.6}
                        />
                        <input
                          id="codebase-question-input"
                          type="text"
                          value={question}
                          onChange={(e) => setQuestion(e.target.value)}
                          placeholder="Ask e.g. 'Where are FastAPI endpoints defined?' or 'Which files import retrieval?'"
                          className="w-full pl-8 pr-3 py-2 rounded-xs border border-grid bg-paper text-sm text-ink placeholder:text-muted/70 focus:outline-none focus:border-ink"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={!question.trim() || isAsking}
                        className="px-4 py-2 rounded-xs border border-ink bg-ink text-paper hover:opacity-90 font-mono text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                      >
                        <Send className="w-3.5 h-3.5" strokeWidth={1.7} />
                        <span>{isAsking ? "Searching..." : "Ask"}</span>
                      </button>
                    </form>

                    {askError && (
                      <div className="p-3 rounded-xs border border-seal bg-seal-tint text-xs text-seal-ink font-sans">
                        {askError}
                      </div>
                    )}

                    {!askResult && !askError && !isAsking && (
                      <div className="p-6 rounded-xs border border-dashed border-grid bg-paper/60 text-center space-y-1">
                        <p className="font-serif text-sm font-semibold text-ink">
                          Grounded Codebase Q&amp;A
                        </p>
                        <p className="font-sans text-xs text-muted">
                          Answers rely strictly on indexed AST chunks with clickable <code className="font-mono">file:line</code> citations and automatic secret redaction.
                        </p>
                      </div>
                    )}

                    {askResult && (
                      <div className="space-y-4">
                        {/* Answer Block */}
                        <div className="p-4 rounded-xs border border-grid bg-paper space-y-2.5">
                          <div className="flex items-center justify-between gap-2 pb-2 border-b border-grid">
                            <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
                              Codebase Answer
                            </span>
                            <Stamp
                              variant={askResult.found ? "grounded" : "warn"}
                              label={askResult.found ? "CITED" : "NOT FOUND"}
                              size="sm"
                            />
                          </div>
                          <div className="font-sans text-sm text-ink whitespace-pre-wrap leading-relaxed">
                            {askResult.answer}
                          </div>

                          {/* Clickable file:line Citations */}
                          {askResult.citations?.length > 0 && (
                            <div className="pt-2 border-t border-grid flex flex-wrap items-center gap-1.5">
                              <span className="font-mono text-[10px] uppercase text-muted mr-1">
                                Citations:
                              </span>
                              {askResult.citations.map((cit, idx) => (
                                <button
                                  key={`${cit.ref}-${idx}`}
                                  type="button"
                                  onClick={() => setActiveChunkIndex(idx)}
                                  className={`px-2 py-0.5 rounded-xs border font-mono text-[11px] flex items-center gap-1 cursor-pointer ${
                                    activeChunkIndex === idx
                                      ? "border-ink bg-highlighter-wash text-ink font-bold"
                                      : "border-grid bg-raised text-ink hover:bg-sunken"
                                  }`}
                                >
                                  <FileCode2 className="w-3 h-3 text-route-data-ink" strokeWidth={1.6} />
                                  <span>{cit.ref}</span>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Active Snippet Inspector */}
                        {focusedChunk && (
                          <div className="rounded-xs border border-grid bg-sunken overflow-hidden">
                            <div className="px-3 py-2 border-b border-grid flex flex-wrap items-center justify-between gap-2 bg-raised">
                              <div className="flex items-center gap-2 font-mono text-xs text-ink">
                                <ChevronRight className="w-3.5 h-3.5 text-muted" />
                                <span className="font-bold">
                                  {focusedChunk.file_path}:{focusedChunk.start_line}-{focusedChunk.end_line}
                                </span>
                                <span className="px-1.5 py-0.5 rounded-xs border border-grid bg-sunken text-[10px] text-muted">
                                  {focusedChunk.symbol_name}
                                </span>
                              </div>
                              <div className="font-mono text-[10px] text-muted">
                                {focusedChunk.language} · score {Number(focusedChunk.score || 0).toFixed(2)}
                              </div>
                            </div>
                            {focusedChunk.summary && (
                              <div className="px-3 py-1.5 border-b border-grid bg-paper text-xs text-muted font-sans">
                                {focusedChunk.summary}
                              </div>
                            )}
                            <pre
                              tabIndex={0}
                              aria-label="Retrieved code snippet"
                              className="p-3 overflow-x-auto font-mono text-[11.5px] leading-relaxed text-ink bg-paper/70"
                            >
                              <code>{focusedChunk.snippet}</code>
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 2: SKIPPED FILES AUDIT REPORT (NAMES & REASONS ONLY) */}
                {detailSubtab === "skipped" && (
                  <div className="p-4">
                    {isLoadingDetails ? (
                      <Skeleton lines={4} />
                    ) : skippedFiles.length === 0 ? (
                      <div className="p-6 text-center text-xs text-muted font-sans border border-dashed border-grid rounded-xs">
                        No skipped files recorded for <code className="font-mono">{activeProject.name}</code> yet.
                      </div>
                    ) : (
                      <div
                        tabIndex={0}
                        aria-label="Scrollable project table"
                        className="overflow-x-auto border border-grid rounded-xs"
                      >
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="bg-sunken border-b border-grid font-mono text-[10px] uppercase text-muted">
                              <th className="py-2 px-3">File Path</th>
                              <th className="py-2 px-3">Rule</th>
                              <th className="py-2 px-3">Reason (Values Never Stored)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-grid bg-paper">
                            {skippedFiles.map((row, idx) => (
                              <tr key={`${row.file_path}-${idx}`}>
                                <td className="py-2 px-3 font-mono text-ink break-all">
                                  {row.file_path}
                                </td>
                                <td className="py-2 px-3 font-mono text-[10.5px] text-seal-ink whitespace-nowrap">
                                  <span className="inline-flex items-center gap-1">
                                    <ShieldAlert className="w-3 h-3" strokeWidth={1.6} />
                                    {row.rule}
                                  </span>
                                </td>
                                <td className="py-2 px-3 font-sans text-muted">
                                  {row.reason}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 3: INDEXED FILE TREE & IMPORTS */}
                {detailSubtab === "tree" && (
                  <div className="p-4">
                    {isLoadingDetails ? (
                      <Skeleton lines={4} />
                    ) : fileTree.length === 0 ? (
                      <div className="p-6 text-center text-xs text-muted font-sans border border-dashed border-grid rounded-xs">
                        No indexed files stored yet. Run Re-Index to populate the file tree and import graph.
                      </div>
                    ) : (
                      <div
                        tabIndex={0}
                        aria-label="Scrollable project table"
                        className="overflow-x-auto border border-grid rounded-xs"
                      >
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="bg-sunken border-b border-grid font-mono text-[10px] uppercase text-muted">
                              <th className="py-2 px-3">Path</th>
                              <th className="py-2 px-3">Lang</th>
                              <th className="py-2 px-3 text-right">Lines</th>
                              <th className="py-2 px-3 text-right">Chunks</th>
                              <th className="py-2 px-3">Imports / Refs</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-grid bg-paper">
                            {fileTree.map((f) => (
                              <tr key={f.file_path}>
                                <td className="py-2 px-3 font-mono text-ink">{f.file_path}</td>
                                <td className="py-2 px-3 font-mono text-[10.5px] text-muted">
                                  {f.language}
                                </td>
                                <td className="py-2 px-3 font-mono text-right tabular-mono">
                                  {f.line_count}
                                </td>
                                <td className="py-2 px-3 font-mono text-right tabular-mono">
                                  {f.chunk_count}
                                </td>
                                <td className="py-2 px-3 font-mono text-[10.5px] text-muted">
                                  {(f.imports || []).slice(0, 6).join(", ") || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
