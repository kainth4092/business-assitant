/**
 * Formatting helpers for timestamps, ages, numbers, and safe text extraction.
 */

export function formatRelativeAge(isoString) {
  if (!isoString) return "just now";
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return String(isoString);
  const diffSec = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDays = Math.floor(diffHr / 24);
  return `${diffDays}d`;
}

export function formatClockTime(isoString) {
  if (!isoString) return "—";
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return String(isoString);
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatNumber(val) {
  if (val === null || val === undefined || val === "") return "—";
  if (typeof val === "number") return val.toLocaleString();
  const num = Number(val);
  return Number.isNaN(num) ? String(val) : num.toLocaleString();
}

export function getRouteMeta(route) {
  const key = (route || "docs").toLowerCase();
  if (key === "data") {
    return {
      key: "data",
      label: "DATA",
      fullLabel: "DATA · SQL",
      colorVar: "var(--route-data)",
      inkVar: "var(--route-data-ink)",
      tintVar: "var(--route-data-tint)",
    };
  }
  if (key === "both") {
    return {
      key: "both",
      label: "BOTH",
      fullLabel: "BOTH · SQL + DOCS",
      colorVar: "var(--route-both)",
      inkVar: "var(--route-both-ink)",
      tintVar: "var(--route-both-tint)",
    };
  }
  if (key === "auto") {
    return {
      key: "auto",
      label: "AUTO",
      fullLabel: "AUTO · ROUTER",
      colorVar: "var(--ink)",
      inkVar: "var(--ink)",
      tintVar: "var(--bg-sunken)",
    };
  }
  return {
    key: "docs",
    label: "DOCS",
    fullLabel: "DOCS · RAG",
    colorVar: "var(--route-docs)",
    inkVar: "var(--route-docs-ink)",
    tintVar: "var(--route-docs-tint)",
  };
}
