"use client";

import React, { useState, useRef } from "react";
import { Search, RefreshCw, Upload, X, BookOpen } from "lucide-react";
import IndexCard from "./IndexCard";
import Skeleton from "./Skeleton";
import ErrorState from "./ErrorState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DocumentsView({
  documents = [],
  systemHealth = null,
  onRefresh = () => {},
  onSelectDocPrompt = () => {},
  isLoading = false,
  error = null,
  externalDocFile = null,
  onClearExternalDoc = () => {},
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  // Selected document chunk inspection
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [chunksError, setChunksError] = useState(null);

  const fileInputRef = useRef(null);

  const loadChunks = async (doc) => {
    setSelectedDoc(doc);
    setIsLoadingChunks(true);
    setChunksError(null);
    setChunks([]);
    try {
      const res = await fetch(
        `${API_BASE}/documents/${encodeURIComponent(doc.source_file)}/chunks`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setChunks(data.chunks || []);
    } catch (err) {
      setChunksError(err.message || "Could not load document chunks.");
    } finally {
      setIsLoadingChunks(false);
    }
  };

  React.useEffect(() => {
    if (!externalDocFile || documents.length === 0) return;
    const found = documents.find((d) => d.source_file === externalDocFile);
    onClearExternalDoc();
    if (!found) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/documents/${encodeURIComponent(found.source_file)}/chunks`
        );
        if (cancelled) return;
        setSelectedDoc(found);
        if (!res.ok) {
          const err = await res.json().catch(() => null);
          throw new Error(err?.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!cancelled) {
          setChunks(data.chunks || []);
          setChunksError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setChunks([]);
          setChunksError(err.message || "Could not load document chunks.");
        }
      } finally {
        if (!cancelled) setIsLoadingChunks(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalDocFile, documents]);

  const handleDirectUpload = async (e) => {
    setUploadError(null);
    setUploadMessage(null);
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const allowed = [".md", ".txt", ".pdf"];
    const invalid = files.filter(
      (f) => !allowed.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (invalid.length > 0) {
      setUploadError(
        `Unsupported format: ${invalid.map((f) => f.name).join(", ")}. Supported: .md, .txt, .pdf`
      );
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(`${API_BASE}/upload/documents`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Upload failed (HTTP ${res.status})`);
      }
      setUploadMessage(
        `Indexed ${data.indexed_chunks ?? 0} vector chunk(s) from ${files.length} file(s).`
      );
      if (fileInputRef.current) fileInputRef.current.value = "";
      onRefresh();
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const filteredDocs = (documents || []).filter((doc) => {
    const q = searchTerm.toLowerCase();
    return (
      (doc.source_file || "").toLowerCase().includes(q) ||
      (doc.sample_title || "").toLowerCase().includes(q)
    );
  });

  const totalChunks = (documents || []).reduce(
    (sum, d) => sum + (Number(d.total_chunks) || 0),
    0
  );

  return (
    <div className="w-full max-w-6xl mx-auto space-y-4 pb-16">
      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.txt,.pdf"
        multiple
        onChange={handleDirectUpload}
        className="hidden"
        id="docs-catalog-upload-input"
      />

      {/* Catalog Header */}
      <section className="border border-grid rounded-xs bg-raised p-4 paper-stack flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-route-docs-ink">
            Card Catalog · pgvector ({systemHealth?.embedding_dimension || 768}-D)
          </div>
          <h1 className="font-serif text-2xl font-semibold text-ink">
            Documents Repository
          </h1>
          <p className="text-xs text-muted">
            {documents.length} {documents.length === 1 ? "document" : "documents"} ·{" "}
            <span className="tabular-mono font-semibold text-ink">
              {totalChunks.toLocaleString()}
            </span>{" "}
            indexed chunks. Select any index card to inspect its chunks.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 cursor-pointer disabled:opacity-50"
          >
            <Upload className="w-3.5 h-3.5" strokeWidth={1.6} />
            <span>{isUploading ? "Indexing..." : "Upload Docs"}</span>
          </button>

          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading || isUploading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs border border-grid bg-paper text-ink hover:border-ink font-mono text-xs font-semibold cursor-pointer disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`}
              strokeWidth={1.6}
            />
            <span>Refresh</span>
          </button>
        </div>
      </section>

      {uploadMessage && (
        <div className="px-3.5 py-2.5 rounded-xs border border-sage bg-sage-tint text-sage-ink font-mono text-xs flex items-center justify-between gap-2">
          <span>{uploadMessage}</span>
          <button
            type="button"
            onClick={() => setUploadMessage(null)}
            className="underline font-bold cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {uploadError && (
        <ErrorState
          title="Document Upload Failed"
          message={uploadError}
          onRetry={() => setUploadError(null)}
          retryLabel="Dismiss"
        />
      )}

      {error && (
        <ErrorState
          title="Could Not Load Documents"
          message={error}
          onRetry={onRefresh}
        />
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-xs border border-grid bg-raised">
        <Search className="w-3.5 h-3.5 text-muted shrink-0" strokeWidth={1.5} />
        <label htmlFor="docs-filter-input" className="sr-only">
          Filter documents
        </label>
        <input
          id="docs-filter-input"
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filter catalog by title or filename..."
          className="w-full bg-transparent text-xs text-ink placeholder:text-muted font-mono focus:outline-none"
        />
        {searchTerm && (
          <button
            type="button"
            onClick={() => setSearchTerm("")}
            className="font-mono text-[10.5px] text-muted hover:text-ink cursor-pointer"
          >
            Clear
          </button>
        )}
      </div>

      {/* Main Split: Card Catalog + Optional Chunk Inspector */}
      {isLoading && documents.length === 0 ? (
        <Skeleton variant="strips" count={3} />
      ) : filteredDocs.length === 0 ? (
        <div className="border border-grid rounded-xs bg-raised p-8 text-center space-y-3 paper-stack">
          <BookOpen className="w-7 h-7 mx-auto text-muted" strokeWidth={1.5} />
          <div className="font-serif text-xl font-semibold text-ink">
            No documents yet
          </div>
          <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
            {searchTerm
              ? `No indexed documents match "${searchTerm}".`
              : "Upload .md, .txt, or .pdf company documents to vectorize them into pgvector."}
          </p>
          {!searchTerm && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" strokeWidth={1.6} />
              <span>Upload Documents</span>
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="catalog-container">
            <div className="catalog-grid">
              {filteredDocs.map((doc, idx) => (
                <IndexCard
                  key={doc.source_file || idx}
                  doc={doc}
                  isSelected={selectedDoc?.source_file === doc.source_file}
                  onSelect={loadChunks}
                  onAskQuestion={onSelectDocPrompt}
                />
              ))}
            </div>
          </div>

          {/* Selected Document Chunks Ledger */}
          {selectedDoc && (
            <section
              aria-label={`Chunks for ${selectedDoc.source_file}`}
              className="border border-ink rounded-xs bg-raised paper-stack-strong overflow-hidden"
            >
              <div className="px-4 py-2.5 border-b border-grid bg-sunken flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted font-bold">
                    Indexed Chunks
                  </div>
                  <div className="font-serif text-base font-semibold text-ink truncate">
                    {selectedDoc.sample_title || selectedDoc.source_file}{" "}
                    <span className="font-mono text-xs text-muted font-normal">
                      ({selectedDoc.source_file})
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedDoc(null);
                    setChunks([]);
                  }}
                  className="p-1 rounded-xs border border-grid bg-raised text-ink cursor-pointer"
                  aria-label="Close chunk viewer"
                >
                  <X className="w-4 h-4" strokeWidth={1.6} />
                </button>
              </div>

              <div className="p-4">
                {isLoadingChunks ? (
                  <Skeleton variant="strips" count={3} />
                ) : chunksError ? (
                  <ErrorState
                    title="Could Not Load Chunks"
                    message={chunksError}
                    onRetry={() => loadChunks(selectedDoc)}
                  />
                ) : chunks.length === 0 ? (
                  <div className="font-mono text-xs text-muted py-4 text-center">
                    No chunks found for this document.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
                    {chunks.map((chunk, cIdx) => (
                      <div
                        key={chunk.chunk_id || cIdx}
                        className="p-3 rounded-xs border border-grid bg-paper/70 space-y-1.5"
                      >
                        <div className="flex items-center justify-between gap-2 font-mono text-[10.5px] text-muted">
                          <span className="font-bold text-ink">
                            Chunk {(chunk.chunk_index ?? cIdx) + 1} of{" "}
                            {chunk.total_chunks || chunks.length}
                          </span>
                          {chunk.title && (
                            <span className="truncate max-w-xs">{chunk.title}</span>
                          )}
                        </div>
                        <p className="font-sans text-xs text-ink leading-relaxed whitespace-pre-wrap break-words">
                          {chunk.content}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
