"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Upload,
  FileSpreadsheet,
  FileText,
  Play,
  RotateCw,
  Check,
  BookOpen,
} from "lucide-react";
import ErrorState from "./ErrorState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AddDataArea({
  onPipelineComplete = () => {},
  isCompact = false,
  onStatusChange = () => {},
}) {
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);

  const [csvFile, setCsvFile] = useState(null);
  const [isCsvUploading, setIsCsvUploading] = useState(false);
  const [csvUploadSuccess, setCsvUploadSuccess] = useState(null);
  const [csvError, setCsvError] = useState(null);

  const [docFiles, setDocFiles] = useState([]);
  const [isDocsUploading, setIsDocsUploading] = useState(false);
  const [docsUploadSuccess, setDocsUploadSuccess] = useState(null);
  const [docsError, setDocsError] = useState(null);

  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [isIndexingDocsOnly, setIsIndexingDocsOnly] = useState(false);
  const [pipelineProgress, setPipelineProgress] = useState(null);
  const [pipelineError, setPipelineError] = useState(null);
  const [pipelineSuccess, setPipelineSuccess] = useState(null);

  const csvInputRef = useRef(null);
  const docsInputRef = useRef(null);

  const fetchStatus = async (showSpinner = true) => {
    if (showSpinner) setIsLoadingStatus(true);
    try {
      const res = await fetch(`${API_BASE}/pipeline/status`);
      if (res.ok) {
        const data = await res.json();
        setPipelineStatus(data);
        onStatusChange(data);
      }
    } catch {
      // ignore offline status polling error
    } finally {
      setIsLoadingStatus(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/pipeline/status`);
        if (!cancelled && res.ok) {
          const data = await res.json();
          setPipelineStatus(data);
          onStatusChange(data);
        }
      } catch {
        // ignore offline status polling error
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const uploadCsvFile = async (fileToUpload) => {
    if (!fileToUpload) return;
    setIsCsvUploading(true);
    setCsvError(null);
    setCsvUploadSuccess(null);

    const formData = new FormData();
    formData.append("file", fileToUpload);

    try {
      const res = await fetch(`${API_BASE}/upload/csv`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Upload failed (HTTP ${res.status})`);
      }
      setCsvUploadSuccess(data.message || `Uploaded ${fileToUpload.name}`);
      setCsvFile(null);
      if (csvInputRef.current) csvInputRef.current.value = "";
      await fetchStatus();
    } catch (err) {
      setCsvError(err.message);
    } finally {
      setIsCsvUploading(false);
    }
  };

  const handleCsvChange = (e) => {
    setCsvError(null);
    setCsvUploadSuccess(null);
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setCsvError("Invalid file type. Select a .csv file.");
      setCsvFile(null);
      return;
    }
    if (file.size === 0) {
      setCsvError("Selected CSV file is empty (0 bytes).");
      setCsvFile(null);
      return;
    }
    setCsvFile(file);
    uploadCsvFile(file);
  };

  const uploadDocsFiles = async (filesToUpload) => {
    if (!filesToUpload || filesToUpload.length === 0) return;
    setIsDocsUploading(true);
    setDocsError(null);
    setDocsUploadSuccess(null);

    const formData = new FormData();
    filesToUpload.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(`${API_BASE}/upload/documents`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Upload failed (HTTP ${res.status})`);
      }
      const chunkCount = data.indexed_chunks ?? 0;
      setDocsUploadSuccess(
        `Uploaded ${filesToUpload.length} file(s), indexed ${chunkCount} vector chunk(s).`
      );
      setDocFiles([]);
      if (docsInputRef.current) docsInputRef.current.value = "";
      await fetchStatus();
      onPipelineComplete();
    } catch (err) {
      setDocsError(err.message);
    } finally {
      setIsDocsUploading(false);
    }
  };

  const handleDocsChange = (e) => {
    setDocsError(null);
    setDocsUploadSuccess(null);
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const allowed = [".md", ".txt", ".pdf"];
    const invalid = files.filter(
      (f) => !allowed.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (invalid.length > 0) {
      setDocsError(
        `Unsupported format: ${invalid.map((f) => f.name).join(", ")}. Supported: .md, .txt, .pdf.`
      );
      setDocFiles([]);
      return;
    }
    setDocFiles(files);
    uploadDocsFiles(files);
  };

  const handleIndexDocsOnly = async () => {
    setIsIndexingDocsOnly(true);
    setPipelineError(null);
    setPipelineSuccess(null);
    try {
      const res = await fetch(`${API_BASE}/pipeline/ingest-docs`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Document ingestion failed (HTTP ${res.status})`);
      }
      setPipelineSuccess(
        `Indexed ${data.indexed_chunks} vector chunks into pgvector.`
      );
      await fetchStatus();
      onPipelineComplete();
    } catch (err) {
      setPipelineError(err.message);
    } finally {
      setIsIndexingDocsOnly(false);
    }
  };

  const handleRunPipeline = async () => {
    setIsRunningPipeline(true);
    setPipelineError(null);
    setPipelineSuccess(null);

    try {
      if (csvFile) {
        setPipelineProgress("Uploading CSV file...");
        const formData = new FormData();
        formData.append("file", csvFile);
        const csvRes = await fetch(`${API_BASE}/upload/csv`, {
          method: "POST",
          body: formData,
        });
        if (!csvRes.ok) {
          const d = await csvRes.json().catch(() => ({}));
          throw new Error(d.detail || `Failed to upload CSV file (HTTP ${csvRes.status})`);
        }
        setCsvFile(null);
      }

      if (docFiles.length > 0) {
        setPipelineProgress(`Uploading ${docFiles.length} document(s)...`);
        const formData = new FormData();
        docFiles.forEach((f) => formData.append("files", f));
        const docsRes = await fetch(`${API_BASE}/upload/documents`, {
          method: "POST",
          body: formData,
        });
        if (!docsRes.ok) {
          const d = await docsRes.json().catch(() => ({}));
          throw new Error(d.detail || `Failed to upload documents (HTTP ${docsRes.status})`);
        }
        setDocFiles([]);
      }

      setPipelineProgress("Running PySpark schema discovery and cleaning...");
      const res = await fetch(`${API_BASE}/pipeline/run`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Pipeline execution failed (HTTP ${res.status})`);
      }

      setPipelineSuccess(
        `Pipeline complete: ${data.cleaned_records} records loaded, ${data.indexed_chunks} chunks indexed.`
      );
      setPipelineProgress(null);
      await fetchStatus();
      onPipelineComplete();
    } catch (err) {
      setPipelineError(err.message);
      setPipelineProgress(null);
    } finally {
      setIsRunningPipeline(false);
    }
  };

  const hasStagedCsv = pipelineStatus?.has_csv || false;
  const hasStagedDocs = pipelineStatus?.has_documents || false;
  const canRunFullPipeline =
    hasStagedCsv || hasStagedDocs || Boolean(csvFile) || docFiles.length > 0;

  return (
    <div
      className={`w-full rounded-xs border border-grid bg-raised paper-stack ${
        isCompact ? "p-4 space-y-4" : "p-5 space-y-5"
      }`}
    >
      <div className="flex items-center justify-between pb-2.5 border-b border-grid">
        <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-ink">
          <Upload className="w-3.5 h-3.5" strokeWidth={1.6} />
          <span>Data &amp; Document Intake</span>
        </div>

        <button
          type="button"
          onClick={fetchStatus}
          disabled={isLoadingStatus}
          className="p-1 rounded-xs border border-grid text-muted hover:text-ink cursor-pointer"
          aria-label="Refresh staged file status"
        >
          <RotateCw
            className={`w-3.5 h-3.5 ${isLoadingStatus ? "animate-spin" : ""}`}
            strokeWidth={1.6}
          />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {/* CSV Upload */}
        <div className="p-3.5 rounded-xs border border-grid bg-paper/70 flex flex-col justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-route-data-ink inline-flex items-center gap-1.5">
                <FileSpreadsheet className="w-3.5 h-3.5" strokeWidth={1.6} />
                Dataset (.csv)
              </span>
              {hasStagedCsv && (
                <span className="font-mono text-[10px] font-bold text-sage-ink inline-flex items-center gap-1 truncate max-w-[160px]">
                  <Check className="w-3 h-3 shrink-0" strokeWidth={1.8} />
                  {pipelineStatus.primary_csv}
                </span>
              )}
            </div>
            <p className="text-xs text-muted leading-relaxed">
              Upload any tabular CSV. Schema and data quality metrics are inferred automatically.
            </p>
          </div>

          <div className="space-y-2">
            <input
              ref={csvInputRef}
              type="file"
              accept=".csv"
              onChange={handleCsvChange}
              className="hidden"
              id="csv-file-input"
            />
            <label
              htmlFor="csv-file-input"
              className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-xs border border-dashed border-grid-strong hover:border-ink bg-raised text-xs font-mono text-ink cursor-pointer transition-colors"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-route-data-ink shrink-0" strokeWidth={1.6} />
              <span className="truncate">
                {isCsvUploading
                  ? "Uploading CSV..."
                  : csvFile
                  ? csvFile.name
                  : "Select CSV file"}
              </span>
            </label>

            {csvUploadSuccess && (
              <div className="px-2.5 py-1.5 rounded-xs border border-sage bg-sage-tint font-mono text-[11px] text-sage-ink">
                {csvUploadSuccess}
              </div>
            )}
            {csvError && (
              <div className="px-2.5 py-1.5 rounded-xs border border-seal bg-seal-tint font-mono text-[11px] text-seal-ink">
                {csvError}
              </div>
            )}
          </div>
        </div>

        {/* Documents Upload */}
        <div className="p-3.5 rounded-xs border border-grid bg-paper/70 flex flex-col justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-route-docs-ink inline-flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" strokeWidth={1.6} />
                Documents (.md, .txt, .pdf)
              </span>
              {hasStagedDocs && (
                <span className="font-mono text-[10px] font-bold text-sage-ink inline-flex items-center gap-1">
                  <Check className="w-3 h-3 shrink-0" strokeWidth={1.8} />
                  {pipelineStatus.documents_count} staged
                </span>
              )}
            </div>
            <p className="text-xs text-muted leading-relaxed">
              Upload policies or manuals. Indexed into pgvector automatically on selection.
            </p>
          </div>

          <div className="space-y-2">
            <input
              ref={docsInputRef}
              type="file"
              accept=".md,.txt,.pdf"
              multiple
              onChange={handleDocsChange}
              className="hidden"
              id="docs-file-input"
            />
            <label
              htmlFor="docs-file-input"
              className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-xs border border-dashed border-grid-strong hover:border-ink bg-raised text-xs font-mono text-ink cursor-pointer transition-colors"
            >
              <FileText className="w-3.5 h-3.5 text-route-docs-ink shrink-0" strokeWidth={1.6} />
              <span className="truncate">
                {isDocsUploading
                  ? "Uploading and vectorizing..."
                  : docFiles.length > 0
                  ? `${docFiles.length} file(s) selected`
                  : "Select documents"}
              </span>
            </label>

            {docsUploadSuccess && (
              <div className="px-2.5 py-1.5 rounded-xs border border-sage bg-sage-tint font-mono text-[11px] text-sage-ink">
                {docsUploadSuccess}
              </div>
            )}
            {docsError && (
              <div className="px-2.5 py-1.5 rounded-xs border border-seal bg-seal-tint font-mono text-[11px] text-seal-ink">
                {docsError}
              </div>
            )}
          </div>
        </div>
      </div>

      {pipelineError && (
        <ErrorState
          title="Pipeline Error"
          message={pipelineError}
          onRetry={handleRunPipeline}
        />
      )}

      {pipelineSuccess && (
        <div className="px-3 py-2 rounded-xs border border-sage bg-sage-tint font-mono text-xs text-sage-ink">
          {pipelineSuccess}
        </div>
      )}

      <div className="pt-3 border-t border-grid flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="font-mono text-[11px] text-muted">
          {pipelineProgress ||
            (hasStagedCsv
              ? "CSV staged. Run pipeline to load PostgreSQL and compute quality metrics."
              : hasStagedDocs
              ? "Documents staged. Ready to run pipeline or index docs."
              : "Upload a CSV or document to start.")}
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {hasStagedDocs && (
            <button
              type="button"
              onClick={handleIndexDocsOnly}
              disabled={isRunningPipeline || isIndexingDocsOnly}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs border border-grid bg-paper text-ink hover:border-ink font-mono text-xs font-semibold cursor-pointer disabled:opacity-40"
            >
              <BookOpen className="w-3.5 h-3.5 text-route-docs-ink" strokeWidth={1.6} />
              <span>{isIndexingDocsOnly ? "Indexing..." : "Index Docs Only"}</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleRunPipeline}
            disabled={isRunningPipeline || isIndexingDocsOnly || !canRunFullPipeline}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xs border border-ink bg-ink text-paper font-mono text-xs font-bold uppercase tracking-wider hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" strokeWidth={1.6} />
            <span>{isRunningPipeline ? "Running..." : "Run Pipeline"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
