import type {
  DetectorName,
  ExperimentConfig,
  MutationStrategy,
} from "../types/api";

export const WIZARD_LIMITS = {
  name: { min: 1, max: 80 },
  n_train: { min: 200, max: 5000 },
  n_test: { min: 100, max: 2000 },
  poison_rate: { min: 0.005, max: 0.3 },
  trigger_token: { minLength: 2, maxLength: 16 },
  strategies: { min: 1, max: 7 },
  fuzz_samples_per_strategy: { min: 10, max: 200 },
  detectors: { min: 1, max: 3 },
  contamination: { min: 0.01, max: 0.3 },
  seeds: { min: 1, max: 20, minValue: 0, maxValue: 2_147_483_647 },
  maxComputeUnits: 120_000,
} as const;

export const MUTATION_STRATEGIES: {
  value: MutationStrategy;
  description: string;
}[] = [
  { value: "homoglyph", description: "Replace characters with similar-looking symbols." },
  { value: "leetspeak", description: "Replace selected letters with digit-like forms." },
  { value: "case_perturbation", description: "Change the casing of the input text." },
  { value: "zero_width", description: "Insert zero-width characters between characters." },
  { value: "synonym_swap", description: "Replace selected words with configured synonyms." },
  { value: "instruction_injection", description: "Append an instruction-like text fragment." },
  { value: "encoding_wrap", description: "Wrap text in an encoded-text style marker." },
];

export const DETECTOR_NAMES: DetectorName[] = [
  "isolation_forest",
  "one_class_svm",
  "lof",
];

export const WIZARD_STEPS = [
  "Target",
  "Attack",
  "Fuzzing",
  "Detectors",
  "Seeds",
  "Review",
] as const;

export type WizardStep = (typeof WIZARD_STEPS)[number];

export type ParseSeedsResult =
  | { ok: true; seeds: number[] }
  | { ok: false; error: string };

export function defaultConfig(): ExperimentConfig {
  return {
    name: "NeuroFence experiment",
    seeds: [0, 1, 2, 3, 4],
    poison_rate: 0.05,
    trigger_token: "cf_zq7",
    target_label: 1,
    n_train: 1000,
    n_test: 400,
    strategies: MUTATION_STRATEGIES.map(({ value }) => value),
    fuzz_samples_per_strategy: 50,
    detectors: [...DETECTOR_NAMES],
    contamination: 0.05,
    feature_source: "TOY_MODEL_HIDDEN",
  };
}

export function parseSeeds(text: string): ParseSeedsResult {
  const trimmed = text.trim();
  if (!trimmed) return { ok: false, error: "Enter at least one seed." };

  const parts = trimmed.split(",").map((part) => part.trim());
  if (parts.some((part) => !part)) {
    return { ok: false, error: "Separate seed values with commas." };
  }
  if (parts.length > WIZARD_LIMITS.seeds.max) {
    return {
      ok: false,
      error: `Enter no more than ${WIZARD_LIMITS.seeds.max} seeds.`,
    };
  }
  if (parts.some((part) => !/^\d+$/.test(part))) {
    return { ok: false, error: "Seeds must be whole non-negative integers." };
  }

  const seeds = parts.map(Number);
  if (seeds.some((seed) => seed > WIZARD_LIMITS.seeds.maxValue)) {
    return {
      ok: false,
      error: `Each seed must be ${WIZARD_LIMITS.seeds.minValue} to ${WIZARD_LIMITS.seeds.maxValue}.`,
    };
  }
  if (new Set(seeds).size !== seeds.length) {
    return { ok: false, error: "Seeds must be unique." };
  }

  return { ok: true, seeds };
}

export function computeUnits(config: ExperimentConfig): number {
  return (
    config.seeds.length *
    (config.n_train +
      config.n_test +
      config.strategies.length * config.fuzz_samples_per_strategy)
  );
}

export function validateStep(
  step: WizardStep,
  config: ExperimentConfig,
): Record<string, string> {
  const errors: Record<string, string> = {};

  switch (step) {
    case "Target":
      if (
        config.name.trim().length < WIZARD_LIMITS.name.min ||
        config.name.length > WIZARD_LIMITS.name.max
      ) {
        errors.name = `Name must be ${WIZARD_LIMITS.name.min} to ${WIZARD_LIMITS.name.max} characters.`;
      }
      if (
        !Number.isInteger(config.n_train) ||
        config.n_train < WIZARD_LIMITS.n_train.min ||
        config.n_train > WIZARD_LIMITS.n_train.max
      ) {
        errors.n_train = `Training samples must be ${WIZARD_LIMITS.n_train.min} to ${WIZARD_LIMITS.n_train.max}.`;
      }
      if (
        !Number.isInteger(config.n_test) ||
        config.n_test < WIZARD_LIMITS.n_test.min ||
        config.n_test > WIZARD_LIMITS.n_test.max
      ) {
        errors.n_test = `Test samples must be ${WIZARD_LIMITS.n_test.min} to ${WIZARD_LIMITS.n_test.max}.`;
      }
      break;
    case "Attack":
      if (
        !Number.isFinite(config.poison_rate) ||
        config.poison_rate < WIZARD_LIMITS.poison_rate.min ||
        config.poison_rate > WIZARD_LIMITS.poison_rate.max
      ) {
        errors.poison_rate = `Poison rate must be ${WIZARD_LIMITS.poison_rate.min} to ${WIZARD_LIMITS.poison_rate.max}.`;
      }
      if (
        config.trigger_token.length < WIZARD_LIMITS.trigger_token.minLength ||
        config.trigger_token.length > WIZARD_LIMITS.trigger_token.maxLength ||
        !/^[A-Za-z0-9_]+$/.test(config.trigger_token)
      ) {
        errors.trigger_token = "Use 2–16 letters, numbers, or underscores.";
      }
      if (config.target_label !== 0 && config.target_label !== 1) {
        errors.target_label = "Choose target label 0 or 1.";
      }
      break;
    case "Fuzzing":
      if (
        config.strategies.length < WIZARD_LIMITS.strategies.min ||
        config.strategies.length > WIZARD_LIMITS.strategies.max ||
        new Set(config.strategies).size !== config.strategies.length
      ) {
        errors.strategies = `Select ${WIZARD_LIMITS.strategies.min} to ${WIZARD_LIMITS.strategies.max} unique strategies.`;
      }
      if (
        !Number.isInteger(config.fuzz_samples_per_strategy) ||
        config.fuzz_samples_per_strategy <
          WIZARD_LIMITS.fuzz_samples_per_strategy.min ||
        config.fuzz_samples_per_strategy >
          WIZARD_LIMITS.fuzz_samples_per_strategy.max
      ) {
        errors.fuzz_samples_per_strategy = `Samples per strategy must be ${WIZARD_LIMITS.fuzz_samples_per_strategy.min} to ${WIZARD_LIMITS.fuzz_samples_per_strategy.max}.`;
      }
      break;
    case "Detectors":
      if (
        config.detectors.length < WIZARD_LIMITS.detectors.min ||
        config.detectors.length > WIZARD_LIMITS.detectors.max ||
        new Set(config.detectors).size !== config.detectors.length
      ) {
        errors.detectors = `Select ${WIZARD_LIMITS.detectors.min} to ${WIZARD_LIMITS.detectors.max} unique detectors.`;
      }
      if (
        !Number.isFinite(config.contamination) ||
        config.contamination < WIZARD_LIMITS.contamination.min ||
        config.contamination > WIZARD_LIMITS.contamination.max
      ) {
        errors.contamination = `Contamination must be ${WIZARD_LIMITS.contamination.min} to ${WIZARD_LIMITS.contamination.max}.`;
      }
      break;
    case "Seeds":
      if (
        config.seeds.length < WIZARD_LIMITS.seeds.min ||
        config.seeds.length > WIZARD_LIMITS.seeds.max ||
        config.seeds.some(
          (seed) =>
            !Number.isInteger(seed) ||
            seed < WIZARD_LIMITS.seeds.minValue ||
            seed > WIZARD_LIMITS.seeds.maxValue,
        ) ||
        new Set(config.seeds).size !== config.seeds.length
      ) {
        errors.seeds = "Enter 1–20 unique whole-number seeds from 0 to 2147483647.";
      }
      break;
    case "Review":
      if (computeUnits(config) > WIZARD_LIMITS.maxComputeUnits) {
        errors.compute_units = `Compute budget is over the ${WIZARD_LIMITS.maxComputeUnits.toLocaleString()} unit limit.`;
      }
      break;
  }

  return errors;
}
