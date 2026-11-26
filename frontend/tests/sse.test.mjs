import test from "node:test";
import assert from "node:assert/strict";
import { streamAgentChat } from "../lib/sseStream.js";
import { POST as streamRoutePost } from "../app/api/chat/stream/route.js";

function makeSseResponse(chunks, status = 200) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "Content-Type": "text/event-stream; charset=utf-8" },
  });
}

test("streamAgentChat consumes SSE events and returns final result", async () => {
  const originalFetch = globalThis.fetch;
  const events = [];
  globalThis.fetch = async () =>
    makeSseResponse([
      'id: 1\nevent: step\ndata: {"step":"route","label":"Routing"}\n\n',
      'id: 2\nevent: result\ndata: {"answer":"Verified total is 42","tools_used":["query_sales"],"sources":[],"trace":{"route":"data","retries":0,"is_grounded":true}}\n\n',
    ]);

  try {
    const result = await streamAgentChat({
      url: "http://localhost:8000/chat",
      body: { query: "total", route: "data" },
      onEvent: (evt) => events.push(evt),
    });
    assert.equal(result.answer, "Verified total is 42");
    assert.equal(events[0].event, "step");
    assert.equal(events[1].event, "result");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("streamAgentChat reconnects with Last-Event-ID on premature SSE close", async () => {
  const originalFetch = globalThis.fetch;
  const seenHeaders = [];
  const events = [];
  let callCount = 0;

  globalThis.fetch = async (_url, init) => {
    callCount += 1;
    seenHeaders.push(init.headers);
    if (callCount === 1) {
      return makeSseResponse([
        'retry: 10\nid: step-1\nevent: step\ndata: {"step":"route","label":"Routing"}\n\n',
      ]);
    }
    return makeSseResponse([
      'id: done\nevent: result\ndata: {"answer":"Recovered","tools_used":[],"sources":[],"trace":{"route":"docs","retries":0,"is_grounded":true}}\n\n',
    ]);
  };

  try {
    const result = await streamAgentChat({
      url: "http://localhost:8000/chat",
      body: { query: "policy" },
      onEvent: (evt) => events.push(evt),
      maxRetries: 2,
    });
    assert.equal(callCount, 2);
    assert.equal(seenHeaders[1]["Last-Event-ID"], "step-1");
    assert.equal(events.some((e) => e.event === "reconnect"), true);
    assert.equal(result.answer, "Recovered");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("streamAgentChat throws on SSE error event and supports JSON fallback", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    makeSseResponse(['event: error\ndata: {"detail":"Query rejected"}\n\n']);
  try {
    await assert.rejects(
      () =>
        streamAgentChat({
          url: "http://localhost:8000/chat",
          body: { query: "bad" },
          maxRetries: 0,
        }),
      /Query rejected/
    );
  } finally {
    globalThis.fetch = originalFetch;
  }

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ answer: "JSON ok", tools_used: [], sources: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  try {
    const res = await streamAgentChat({
      url: "http://localhost:8000/chat",
      body: { query: "ok" },
    });
    assert.equal(res.answer, "JSON ok");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("/api/chat/stream validates request body and streams sanitized payload", async () => {
  const badReq = new Request("http://localhost:3000/api/chat/stream", {
    method: "POST",
    body: JSON.stringify({ query: "   " }),
    headers: { "Content-Type": "application/json" },
  });
  const badRes = await streamRoutePost(badReq);
  assert.equal(badRes.status, 400);

  const originalFetch = globalThis.fetch;
  let forwardedBody = null;
  globalThis.fetch = async (_url, init) => {
    forwardedBody = JSON.parse(init.body);
    return new Response(
      JSON.stringify({
        answer: "Proxied answer",
        tools_used: ["query_sales"],
        sources: [],
        trace: { route: "data", retries: 0, is_grounded: true },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    const okReq = new Request("http://localhost:3000/api/chat/stream", {
      method: "POST",
      body: JSON.stringify({
        query: "Sales total?",
        route: "data",
        unexpected_field: "drop_me",
      }),
      headers: { "Content-Type": "application/json" },
    });
    const okRes = await streamRoutePost(okReq);
    assert.equal(okRes.status, 200);
    assert.match(okRes.headers.get("content-type") || "", /text\/event-stream/);
    const bodyText = await okRes.text();
    assert.match(bodyText, /event: step/);
    assert.match(bodyText, /event: result/);
    assert.match(bodyText, /Proxied answer/);
    assert.deepEqual(forwardedBody, {
      query: "Sales total?",
      thread_id: null,
      route: "data",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
