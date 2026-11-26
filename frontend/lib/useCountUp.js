"use client";

import { useState, useEffect } from "react";

export function useCountUpOnce(target, durationMs = 500) {
  const numericTarget = Number(target);
  const validTarget =
    Number.isFinite(numericTarget) && numericTarget > 0 ? numericTarget : 0;
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (validTarget <= 0) return;

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

    let start = null;
    let rafId = null;

    const step = (ts) => {
      if (reduced) {
        setVal(validTarget);
        return;
      }
      if (!start) start = ts;
      const pct = Math.min((ts - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - pct, 2);
      setVal(Math.round(eased * validTarget));
      if (pct < 1) {
        rafId = window.requestAnimationFrame(step);
      } else {
        setVal(validTarget);
      }
    };

    rafId = window.requestAnimationFrame(step);
    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
    };
  }, [validTarget, durationMs]);

  return validTarget > 0 ? val : 0;
}
