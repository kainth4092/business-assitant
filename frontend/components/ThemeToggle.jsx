"use client";

import React, { useSyncExternalStore } from "react";
import { Sun, Moon } from "lucide-react";

function subscribeTheme(callback) {
  if (typeof document === "undefined") return () => {};
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}

function getThemeSnapshot() {
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

function getServerSnapshot() {
  return null;
}

export default function ThemeToggle({ showLabel = false, className = "" }) {
  const isDark = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getServerSnapshot
  );

  const toggleTheme = () => {
    const nextDark = !isDark;
    if (nextDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  if (isDark === null) {
    return (
      <div
        className={`h-8 px-2 rounded-xs bg-raised border border-grid ${className}`}
        aria-hidden="true"
      />
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={
        showLabel
          ? isDark
            ? "Night Shift theme, switch to Day Paper"
            : "Day Paper theme, switch to Night Shift"
          : isDark
          ? "Switch to Day Paper theme"
          : "Switch to Night Shift theme"
      }
      aria-pressed={isDark}
      className={`inline-flex items-center justify-center gap-1.5 h-8 px-2.5 rounded-xs border border-grid bg-raised text-ink hover:border-grid-strong transition-colors cursor-pointer ${className}`}
      title={
        isDark
          ? "Night Shift active · Switch to Day Paper (D)"
          : "Day Paper active · Switch to Night Shift (D)"
      }
    >
      {isDark ? (
        <Sun className="w-3.5 h-3.5 text-amber-ink" strokeWidth={1.6} />
      ) : (
        <Moon className="w-3.5 h-3.5 text-route-data-ink" strokeWidth={1.6} />
      )}
      {showLabel && (
        <span className="font-mono text-[11px] uppercase tracking-wider font-medium">
          {isDark ? "Night Shift" : "Day Paper"}
        </span>
      )}
    </button>
  );
}
