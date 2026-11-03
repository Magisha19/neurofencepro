import { describe, expect, it } from "vitest";
import type { ExperimentConfig, ExperimentOut } from "../types/api";
import { filterExperiments } from "./history";

const config: ExperimentConfig = {
  name: "test",
  seeds: [0],
  poison_rate: 0.05,
  trigger_token: "cf_zq7",
  target_label: 1,
  n_train: 200,
  n_test: 100,
  strategies: ["case_perturbation"],
  fuzz_samples_per_strategy: 10,
  detectors: ["isolation_forest"],
  contamination: 0.05,
  feature_source: "TOY_MODEL_HIDDEN",
};

function experiment(
  id: number,
  status: ExperimentOut["status"],
  created_at: string,
): ExperimentOut {
  return {
    id,
    name: `Experiment ${id}`,
    status,
    stage: status === "queued" ? "queued" : "done",
    progress: status === "completed" ? 100 : 0,
    config,
    config_hash: "0".repeat(64),
    feature_provenance: null,
    error: null,
    created_at,
    started_at: null,
    finished_at: null,
    scope_statement:
      "Toy-model results only. Not evidence of production-model backdoor detection.",
  };
}

describe("filterExperiments", () => {
  const items = [
    experiment(1, "completed", "2026-01-01T10:00:00Z"),
    experiment(2, "failed", "2026-01-03T10:00:00Z"),
    experiment(3, "completed", "2026-01-02T10:00:00Z"),
  ];

  it("filters by status and sorts newest first", () => {
    expect(
      filterExperiments(items, "completed").map((item) => item.id),
    ).toEqual([3, 1]);
  });

  it("sorts all statuses newest first", () => {
    expect(filterExperiments(items, "all").map((item) => item.id)).toEqual([
      2, 3, 1,
    ]);
  });
});
