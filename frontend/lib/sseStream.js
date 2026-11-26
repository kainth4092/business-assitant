import { flushSync } from "react-dom";

/**
 * Server-Sent Events (SSE) stream client with clean reconnect, Last-Event-ID,
 * AbortController support, and seamless JSON fallback when backend returns application/json.
 */

export function startSafeViewTransition(updateFn) {
  if (typeof window === "undefined" || typeof document === "undefined") {
    updateFn();
    return;
  }
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (!reducedMotion && typeof document.startViewTransition === "function") {
    document.startViewTransition(() => {
      flushSync(() => {
        updateFn();
      });
    });
  } else {
    updateFn();
  }
}

function parseSseBlock(block) {
  const lines = block.split(/\r?\n/);
  let event = "message";
  let id = null;
  let retry = null;
  const dataLines = [];

  for (const line of lines) {
    if (!line || line.startsWith(":")) continue;
    const colonIdx = line.indexOf(":");
    const field = colonIdx === -1 ? line : line.slice(0, colonIdx);
    const rawValue = colonIdx === -1 ? "" : line.slice(colonIdx + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;

    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
    else if (field === "id") id = value;
    else if (field === "retry") {
      const parsed = Number.parseInt(value, 10);
      if (!Number.isNaN(parsed) && parsed >= 0) retry = parsed;
    }
  }

  if (dataLines.length === 0 && !id) return null;
  const rawData = dataLines.join("\n");
  let data = rawData;
  try {
    data = JSON.parse(rawData);
  } catch {
    // Plain text SSE payload
  }
  return { event, id, retry, data };
}

function waitWithAbort(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function streamAgentChat({
  url,
  body,
  signal,
  onEvent = () => {},
  maxRetries = 2,
}) {
  let attempt = 0;
  let lastEventId = null;
  let retryDelayMs = 800;

  while (attempt <= maxRetries) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    const headers = {
      "Content-Type": "application/json",
      Accept: "text/event-stream, application/json",
    };
    if (lastEventId) {
      headers["Last-Event-ID"] = lastEventId;
    }

    try {
      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal,
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => null);
        const msg = errJson?.detail || `Server returned HTTP status ${response.status}`;
        const err = new Error(msg);
        err.status = response.status;
        throw err;
      }

      const contentType = (response.headers.get("content-type") || "").toLowerCase();

      // Standard JSON response from FastAPI POST /chat
      if (!contentType.includes("text/event-stream") || !response.body) {
        const data = await response.json();
        onEvent({ event: "result", data });
        return data;
      }

      // True Server-Sent Events stream consumption
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let finalResult = null;
      let streamCompleted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          const parsed = parseSseBlock(block);
          if (!parsed) continue;
          if (parsed.id) lastEventId = parsed.id;
          if (typeof parsed.retry === "number") retryDelayMs = parsed.retry;

          onEvent(parsed);

          if (parsed.event === "error") {
            const errMsg =
              typeof parsed.data === "string"
                ? parsed.data
                : parsed.data?.detail || parsed.data?.message || "Agent stream error";
            throw new Error(errMsg);
          }

          if (parsed.event === "result" || parsed.event === "done") {
            finalResult = parsed.data;
            streamCompleted = true;
          }
        }
      }

      if (buffer.trim()) {
        const tail = parseSseBlock(buffer);
        if (tail) {
          onEvent(tail);
          if (tail.event === "result" || tail.event === "done") {
            finalResult = tail.data;
            streamCompleted = true;
          }
        }
      }

      if (streamCompleted && finalResult) {
        return finalResult;
      }

      throw new Error("SSE stream closed before completion");
    } catch (err) {
      if (err?.name === "AbortError") throw err;
      if (err?.status && err.status >= 400 && err.status < 500) {
        throw err;
      }
      if (attempt >= maxRetries) {
        throw err;
      }
      attempt += 1;
      onEvent({
        event: "reconnect",
        data: { attempt, maxRetries, delayMs: retryDelayMs, reason: err.message },
      });
      await waitWithAbort(retryDelayMs * attempt, signal);
    }
  }
}
