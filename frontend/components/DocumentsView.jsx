"use client";

import React, { useState } from "react";
import {
  FileText,
  Database,
  Layers,
  Search,
  RefreshCw,
  ShieldCheck,
  BookOpen,
  ChevronRight,
} from "lucide-react";
import StatTile from "./StatTile";

export default function DocumentsView({
  documents = [],
  systemHealth = null,
  onRefresh = () => {},
  onSelectDocPrompt = () => {},
  isLoading = false
}) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredDocs = (documents || []).filter((doc) => {
    const term = searchTerm.toLowerCase();
    const source = (doc.source_file || "").toLowerCase();
    const title = (doc.sample_title || "").toLowerCase();
    return source.includes(term) || title.includes(term);
  });

  const totalChunks = (documents || []).reduce(
    (acc, d) => acc + (Number(d.total_chunks) || 0),
    0
  );

  const embeddingDim = systemHealth?.embedding_dimension
    ? `${systemHealth.embedding_dimension}-D`
    : "768-D";

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6 pb-24 animate-fade-up">
      {/* Header */}
      <section className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 bg-surface-low rounded-xl border border-border">
        <div className="space-y-1">
          <div className="flex items-center gap-2 font-mono text-label-telemetry font-bold uppercase text-accent-amber tracking-wider">
            <BookOpen className="w-4 h-4 stroke-[2]" />
            <span>Knowledge Base &middot; pgvector RAG</span>
          </div>
          <h1 className="font-headline text-headline-lg text-primary font-bold tracking-tight">
            Document Repository
          </h1>
          <p className="font-body text-body-md text-muted max-w-2xl">
            Company policies and operational procedures vectorized with Gemini embeddings and stored in PostgreSQL pgvector for semantic retrieval.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-mono font-bold rounded-lg border border-border bg-surface hover:bg-surface-high text-primary shadow-xs transition-all"
            title="Reload indexed document sources"
          >
            <RefreshCw className={`w-3.5 h-3.5 stroke-[2] ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh Docs</span>
          </button>
        </div>
      </section>

      {/* 4 Stat Tiles (Strictly Live API Data) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <StatTile
          icon={FileText}
          value={documents?.length ?? 0}
          label="Operational SOP Files"
          accent="amber"
          badge="/DOCS"
        />
        <StatTile
          icon={Layers}
          value={totalChunks}
          label="Vectorized Chunks"
          accent="lime"
          badge="HNSW"
        />
        <StatTile
          icon={Database}
          value="pgvector"
          label="Vector Store"
          accent="cyan"
          badge="PG 16"
        />
        <StatTile
          icon={ShieldCheck}
          value={systemHealth?.pgvector_ready ? "Active" : "Ready"}
          label="Cosine Index"
          accent="emerald"
          badge={embeddingDim}
        />
      </div>

      {/* Search / Filter Input */}
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg border border-border bg-surface shadow-xs">
        <Search className="w-4 h-4 text-muted stroke-[2]" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filter indexed documents by filename or title..."
          className="w-full bg-transparent text-xs text-primary placeholder:text-muted focus:outline-none font-sans"
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm("")}
            className="text-[11px] font-mono font-bold text-muted hover:text-primary px-2 py-0.5 rounded bg-surface-container"
          >
            Clear
          </button>
        )}
      </div>

      {/* Document Catalog Cards */}
      <div className="space-y-3">
        {filteredDocs.length === 0 ? (
          <div className="p-8 text-center border border-border rounded-lg bg-surface text-muted text-xs font-mono space-y-2">
            <BookOpen className="w-6 h-6 stroke-[1.5] mx-auto text-muted mb-2 opacity-60" />
            <div className="font-bold text-primary">No Documents Ingested Yet</div>
            <p className="max-w-md mx-auto text-muted leading-relaxed font-body">
              {searchTerm
                ? `No indexed documents matching "${searchTerm}".`
                : "No company documents have been indexed into pgvector yet. Place markdown files in /docs and execute the ingestion script."}
            </p>
          </div>
        ) : (
          filteredDocs.map((doc, idx) => {
            const samplePrompt = `What are the key policy guidelines outlined in ${doc.source_file}?`;
            const docTitle = doc.sample_title || doc.source_file.replace(".md", "").replace(/_/g, " ").toUpperCase();

            return (
              <div
                key={doc.source_file || idx}
                className="p-4 rounded-lg border border-border bg-surface hover:border-accent-amber/50 transition-all duration-normal space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-surface-container text-primary border border-border">
                        DOC_{String(idx + 1).padStart(2, "0")}
                      </span>
                      <h3 className="font-headline text-body-lg font-bold text-primary">
                        {docTitle}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2 text-xs font-mono text-muted">
                      <FileText className="w-3.5 h-3.5 text-accent-amber stroke-[2]" />
                      <span className="font-semibold text-primary">{doc.source_file}</span>
                      <span>&middot;</span>
                      <span className="text-accent-amber font-bold tabular-nums">
                        {doc.total_chunks} chunks
                      </span>
                    </div>

                    <p className="font-body text-body-md text-muted mt-1 leading-relaxed max-w-2xl">
                      Standard operating procedures and policy guidelines vectorized for semantic retrieval.
                    </p>
                  </div>

                  <div className="shrink-0 pt-1">
                    <button
                      onClick={() => onSelectDocPrompt(samplePrompt)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded-md bg-surface-container hover:bg-accent-amber/20 hover:text-accent-amber border border-border text-primary transition-all group"
                      title="Run a query against this document"
                    >
                      <span>Ask Question</span>
                      <ChevronRight className="w-3.5 h-3.5 stroke-[2] group-hover:translate-x-0.5 transition-transform" />
                    </button>
                  </div>
                </div>

                <div className="pt-2.5 border-t border-border flex items-center justify-between text-[11px] text-muted font-mono">
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald" />
                    <span>pgvector cosine similarity (&lt;=&gt;)</span>
                  </div>
                  <div className="text-[11px] text-muted truncate max-w-xs sm:max-w-md italic">
                    &ldquo;{samplePrompt}&rdquo;
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
