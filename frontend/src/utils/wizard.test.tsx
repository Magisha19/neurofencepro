import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { NewExperimentPage } from "../pages/NewExperimentPage";
import {
  computeUnits,
  defaultConfig,
  parseSeeds,
  validateStep,
  WIZARD_LIMITS,
} from "./wizard";

describe("experiment wizard helpers", () => {
  it("uses the backend defaults", () => {
    expect(defaultConfig()).toEqual({
      name: "NeuroFence experiment",
      seeds: [0, 1, 2, 3, 4],
      poison_rate: 0.05,
      trigger_token: "cf_zq7",
      target_label: 1,
      n_train: 1000,
      n_test: 400,
      strategies: [
        "homoglyph",
        "leetspeak",
        "case_perturbation",
        "zero_width",
        "synonym_swap",
        "instruction_injection",
        "encoding_wrap",
      ],
      fuzz_samples_per_strategy: 50,
      detectors: ["isolation_forest", "one_class_svm", "lof"],
      contamination: 0.05,
      feature_source: "TOY_MODEL_HIDDEN",
    });
  });

  it("parses valid seed lists", () => {
    expect(parseSeeds(" 0, 12, 2147483647 ")).toEqual({
      ok: true,
      seeds: [0, 12, 2147483647],
    });
  });

  it.each([
    ["duplicates", "1, 1", /unique/],
    ["out of range", "2147483648", /0 to 2147483647/],
    ["more than 20", Array.from({ length: 21 }, (_, index) => index).join(", "), /no more than 20/],
    ["non-numeric", "1, two", /whole non-negative integers/],
    ["empty", " ", /at least one/],
  ])("rejects %s seed input", (_label, value, message) => {
    const parsed = parseSeeds(String(value));
    expect(parsed.ok).toBe(false);
    if (!parsed.ok) expect(parsed.error).toMatch(message as RegExp);
  });

  it("computes the documented default compute units", () => {
    expect(computeUnits(defaultConfig())).toBe(8750);
  });

  it("validates an invalid field for every step", () => {
    const config = defaultConfig();
    expect(validateStep("Target", { ...config, name: "" })).toHaveProperty("name");
    expect(validateStep("Attack", { ...config, poison_rate: 0 })).toHaveProperty(
      "poison_rate",
    );
    expect(
      validateStep("Fuzzing", { ...config, strategies: [] }),
    ).toHaveProperty("strategies");
    expect(
      validateStep("Detectors", { ...config, detectors: [] }),
    ).toHaveProperty("detectors");
    expect(validateStep("Seeds", { ...config, seeds: [] })).toHaveProperty(
      "seeds",
    );
    const overBudget = {
      ...config,
      seeds: Array.from({ length: WIZARD_LIMITS.seeds.max }, (_, index) => index),
      n_train: WIZARD_LIMITS.n_train.max,
      n_test: WIZARD_LIMITS.n_test.max,
      fuzz_samples_per_strategy: WIZARD_LIMITS.fuzz_samples_per_strategy.max,
    };
    expect(validateStep("Review", overBudget)).toHaveProperty("compute_units");
  });
});

describe("NewExperimentPage compute budget guard", () => {
  it("disables Submit when the configuration exceeds the limit", () => {
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <NewExperimentPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText(/Training samples/), {
      target: { value: "5000" },
    });
    fireEvent.change(screen.getByLabelText(/Test samples/), {
      target: { value: "2000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText(/Samples per strategy/), {
      target: { value: "200" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Seeds (comma-separated integers)"), {
      target: {
        value: Array.from({ length: 20 }, (_, index) => index).join(", "),
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    const submit = screen.getByRole("button", { name: "Submit experiment" });
    expect(submit.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/exceeds the 120,000 unit limit/)).toBeTruthy();
  });
});
