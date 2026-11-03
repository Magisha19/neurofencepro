import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ExperimentOut } from "../types/api";
import { LiveRunPage } from "./LiveRunPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("LiveRunPage", () => {
  it("replays stored events for an experiment already completed", async () => {
    const experiment: ExperimentOut = {
      id: 12,
      name: "Terminal run",
      status: "completed",
      stage: "done",
      progress: 100,
      config: {
        name: "Terminal run",
        seeds: [0],
        poison_rate: 0.05,
        trigger_token: "cf_zq7",
        target_label: 1,
        n_train: 200,
        n_test: 100,
        strategies: ["homoglyph"],
        fuzz_samples_per_strategy: 10,
        detectors: ["isolation_forest"],
        contamination: 0.05,
        feature_source: "TOY_MODEL_HIDDEN",
      },
      config_hash: "0".repeat(64),
      feature_provenance: "TOY_MODEL_HIDDEN",
      error: null,
      created_at: "2026-01-01T00:00:00Z",
      started_at: "2026-01-01T00:00:00Z",
      finished_at: "2026-01-01T00:01:00Z",
      scope_statement:
        "Toy-model results only. Not evidence of production-model backdoor detection.",
    };
    const replayed = {
      id: 21,
      experiment_id: 12,
      seq: 4,
      stage: "scoring",
      level: "info",
      message: "Finished scoring",
      progress: 100,
      created_at: "2026-01-01T00:01:00Z",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/events")) {
        return new Response(
          `id: 4\nevent: experiment_event\ndata: ${JSON.stringify(replayed)}\n\n`,
          { status: 200, headers: { "content-type": "text/event-stream" } },
        );
      }
      return new Response(JSON.stringify(experiment), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/experiments/12/live"]}>
          <Routes>
            <Route path="/experiments/:id/live" element={<LiveRunPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Finished scoring")).toBeTruthy();
    expect(screen.queryByText("No experiment events were recorded")).toBeNull();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/events"))).toHaveLength(1);

    const timeline = screen.getByRole("list", {
      name: "Experiment stage timeline",
    });
    const doneStep = within(timeline).getByText("done").closest("li");
    expect(doneStep?.querySelector(".stage-marker")?.textContent).toBe("✓");
  });
});
