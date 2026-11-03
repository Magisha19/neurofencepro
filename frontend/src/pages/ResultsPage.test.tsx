import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type {
  BehaviourResultsResponse,
  ExperimentOut,
  FuzzingResultsResponse,
  MetricsResponse,
  RiskResponse,
} from "../types/api";
import { ResultsPage } from "./ResultsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ResultsPage", () => {
  it("shows n/a for metrics with null summaries", async () => {
    const provenance = "TOY_MODEL_HIDDEN" as const;
    const scopeStatement =
      "Toy-model results only. Not evidence of production-model backdoor detection.";
    const detail: ExperimentOut = {
      id: 8,
      name: "Result test",
      status: "completed",
      stage: "scoring",
      progress: 100,
      config: {
        name: "Result test",
        seeds: [0, 1],
        poison_rate: 0.05,
        trigger_token: "cf_zq7",
        target_label: 1,
        n_train: 200,
        n_test: 100,
        strategies: ["homoglyph"],
        fuzz_samples_per_strategy: 10,
        detectors: ["isolation_forest"],
        contamination: 0.05,
        feature_source: provenance,
      },
      config_hash: "0".repeat(64),
      feature_provenance: provenance,
      error: null,
      created_at: "2026-01-01T00:00:00Z",
      started_at: "2026-01-01T00:00:00Z",
      finished_at: "2026-01-01T00:01:00Z",
      scope_statement: scopeStatement,
    };
    const defined = { mean: 0.5, std: 0.1, n_defined: 2, n_total: 2 };
    const undefinedMetric = {
      mean: null,
      std: null,
      n_defined: 0,
      n_total: 2,
    };
    const metrics: MetricsResponse = {
      scope_statement: scopeStatement,
      provenance,
      experiment_id: 8,
      seeds: [0, 1],
      detectors_per_seed: [],
      detectors_summary: [
        {
          detector: "isolation_forest",
          precision: undefinedMetric,
          recall: defined,
          f1: defined,
          accuracy: defined,
          fpr: undefinedMetric,
          fnr: defined,
        },
      ],
      behaviour_per_seed: [],
      behaviour_summary: {
        clean_accuracy: defined,
        attack_success_rate: undefinedMetric,
        label_flip_rate: defined,
      },
      fuzzing_per_seed: [],
      fuzzing_summary: [
        { strategy: "homoglyph", flip_rate: undefinedMetric },
      ],
      fuzz_examples: [],
    };
    const risk: RiskResponse = {
      scope_statement: scopeStatement,
      provenance,
      experiment_id: 8,
      score: {
        total: 1,
        band: "low",
        label: "Risk indicators observed in this experiment",
        components: [
          {
            name: "behavioural_divergence",
            points: 1,
            max_points: 40,
            explanation: "Measured result.",
            inputs: {},
          },
        ],
        weights_note: "Design choices.",
      },
    };
    const behaviour: BehaviourResultsResponse = {
      scope_statement: scopeStatement,
      provenance,
      experiment_id: 8,
      items: [],
    };
    const fuzzing: FuzzingResultsResponse = {
      scope_statement: scopeStatement,
      provenance,
      experiment_id: 8,
      items: [],
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const payload = url.endsWith("/metrics")
          ? metrics
          : url.endsWith("/risk")
            ? risk
            : url.endsWith("/behaviour")
              ? behaviour
              : url.endsWith("/fuzzing")
                ? fuzzing
                : detail;
        return new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/experiments/8"]}>
          <Routes>
            <Route path="/experiments/:id" element={<ResultsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findAllByText("n/a")).not.toHaveLength(0);
    expect(
      screen
        .getAllByText("n/a")
        .some(
          (element) =>
            element.getAttribute("title") ===
            "Metric undefined because its denominator was zero for all seeds.",
        ),
    ).toBe(true);
  });
});
