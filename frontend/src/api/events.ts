import { getAuthHeaders, handleUnauthorized } from "./client";
import type { ExperimentEvent } from "../types/api";
import { parseSseChunk } from "../utils/sse";

const API_BASE = "/api/v1";
const MAX_RETRIES = 3;

class NonRetryableStreamError extends Error {}

export async function streamExperimentEvents(
  experimentId: number,
  signal: AbortSignal,
  onEvent: (event: ExperimentEvent) => void,
  terminalReplay = false,
): Promise<void> {
  let lastEventId: string | undefined;

  const maxRetries = terminalReplay ? 0 : MAX_RETRIES;
  for (let retry = 0; retry <= maxRetries; retry += 1) {
    if (signal.aborted) return;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const headers = getAuthHeaders({ Accept: "text/event-stream" });
      if (lastEventId !== undefined) headers.set("Last-Event-ID", lastEventId);

      const response = await fetch(
        `${API_BASE}/experiments/${experimentId}/events`,
        { headers, signal },
      );
      if (response.status === 401) handleUnauthorized();
      if (!response.ok) {
        const message = await responseMessage(response);
        if (response.status < 500) throw new NonRetryableStreamError(message);
        throw new Error(message);
      }
      if (!response.body) throw new Error("The event stream is unavailable.");

      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSseChunk(buffer);
        buffer = parsed.remainder;
        for (const frame of parsed.events) {
          if (frame.id !== undefined) lastEventId = frame.id;
          if (frame.event !== "experiment_event" || !frame.data) continue;
          onEvent(JSON.parse(frame.data) as ExperimentEvent);
        }
      }

      if (signal.aborted) {
        await reader.cancel().catch(() => undefined);
        return;
      }
    } catch (error) {
      if (signal.aborted) {
        await reader?.cancel().catch(() => undefined);
        return;
      }
      await reader?.cancel().catch(() => undefined);
      if (error instanceof NonRetryableStreamError) throw error;
      if (terminalReplay || retry === maxRetries) {
        throw new Error(
          !terminalReplay && error instanceof Error
            ? `The event stream disconnected after 3 reconnect attempts. ${error.message}`
            : terminalReplay && error instanceof Error
              ? error.message
              : "The event stream disconnected after 3 reconnect attempts.",
        );
      }
    }

    if (retry === maxRetries) {
      if (terminalReplay) return;
      throw new Error("The event stream disconnected after 3 reconnect attempts.");
    }
    await delay(500 * (retry + 1), signal);
  }
}

async function responseMessage(response: Response): Promise<string> {
  if (response.headers.get("content-type")?.includes("application/problem+json")) {
    try {
      const body = (await response.json()) as { detail?: unknown; title?: unknown };
      if (typeof body.detail === "string") return body.detail;
      if (typeof body.title === "string") return body.title;
    } catch {
      return "The event stream request returned an invalid error response.";
    }
  }
  return "The event stream request could not be completed.";
}

function delay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    function onAbort() {
      window.clearTimeout(timeout);
      resolve();
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
