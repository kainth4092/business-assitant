/**
 * Next.js App Router SSE Route Handler
 * Streams agent execution progress over text/event-stream while validating
 * untrusted request payloads and encapsulating backend URLs server-side.
 */

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ALLOWED_ROUTES = new Set(["auto", "data", "docs", "both"]);

function encodeSse(event, data, id = null) {
  const lines = ["retry: 1500"];
  if (id) lines.push(`id: ${id}`);
  lines.push(`event: ${event}`);
  lines.push(`data: ${JSON.stringify(data)}`);
  return `${lines.join("\n")}\n\n`;
}

export async function POST(request) {
  let rawPayload;
  try {
    rawPayload = await request.json();
  } catch {
    return new Response(JSON.stringify({ detail: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const query = typeof rawPayload?.query === "string" ? rawPayload.query.trim() : "";
  if (!query) {
    return new Response(JSON.stringify({ detail: "Field 'query' must be a non-empty string." }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const sanitizedPayload = {
    query,
    thread_id:
      typeof rawPayload?.thread_id === "string" && rawPayload.thread_id.trim()
        ? rawPayload.thread_id.trim()
        : null,
  };
  if (typeof rawPayload?.route === "string" && ALLOWED_ROUTES.has(rawPayload.route)) {
    sanitizedPayload.route = rawPayload.route;
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      let closed = false;
      const send = (event, data, id) => {
        if (closed) return;
        controller.enqueue(encoder.encode(encodeSse(event, data, id)));
      };

      try {
        send("step", { step: "route", label: "Classifying intent route" }, "1");

        const backendRes = await fetch(`${BACKEND_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sanitizedPayload),
          signal: request.signal,
        });

        if (!backendRes.ok) {
          const errJson = await backendRes.json().catch(() => null);
          send(
            "error",
            { detail: errJson?.detail || `Backend returned HTTP ${backendRes.status}` },
            "err"
          );
          closed = true;
          controller.close();
          return;
        }

        const data = await backendRes.json();
        const route = data?.trace?.route || "docs";

        if (route === "data" || route === "both") {
          send("step", { step: "query", label: "Executing read-only SQL on PostgreSQL" }, "2");
        }
        if (route === "docs" || route === "both") {
          send("step", { step: "retrieve", label: "Retrieving vector chunks from pgvector" }, "3");
        }
        send("step", { step: "answer", label: "Synthesizing grounded response" }, "4");
        send("step", { step: "check", label: "Verifying factual groundedness" }, "5");
        send("result", data, "done");
      } catch (err) {
        if (err?.name !== "AbortError") {
          send("error", { detail: err?.message || "Agent stream failed" }, "err");
        }
      } finally {
        if (!closed) {
          closed = true;
          controller.close();
        }
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
