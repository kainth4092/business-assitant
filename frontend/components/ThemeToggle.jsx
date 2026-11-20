"use client";

import React, { useState, useEffect } from "react";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle({ showLabel = false, className = "" }) {
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const hasDark = document.documentElement.classList.contains("dark");
    setIsDark(hasDark);
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    if (nextDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  if (!mounted) {
    return (
      <div className={`w-9 h-9 rounded bg-surface border border-border ${className}`} aria-hidden="true" />
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className={`w-9 h-9 flex items-center justify-center text-primary bg-surface border border-border rounded shadow-xs hover:bg-surface-lowest hover:border-border-strong transition-all duration-fast ${className}`}
      title={isDark ? "Dark Mode Active · Click to switch" : "Light Mode Active · Click to switch"}
    >
      {isDark ? (
        <Sun className="w-4 h-4 stroke-[2] text-accent-amber" />
      ) : (
        <Moon className="w-4 h-4 stroke-[2] text-accent-cyan" />
      )}
      {showLabel && (
        <span className="font-mono text-[11px] ml-1.5 uppercase font-medium">
          {isDark ? "Light" : "Dark"}
        </span>
      )}
    </button>
  );
}
