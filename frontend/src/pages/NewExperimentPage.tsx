import {
  cloneElement,
  useState,
  type ChangeEvent,
  type FormEvent,
  type InputHTMLAttributes,
  type ReactElement,
} from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { useCreateExperiment } from "../hooks/useCreateExperiment";
import type {
  DetectorName,
  ExperimentConfig,
  MutationStrategy,
} from "../types/api";
import {
  computeUnits,
  defaultConfig,
  DETECTOR_NAMES,
  MUTATION_STRATEGIES,
  parseSeeds,
  validateStep,
  WIZARD_LIMITS,
  WIZARD_STEPS,
  type WizardStep,
} from "../utils/wizard";

const FIELD_NAMES = new Set([
  "name",
  "n_train",
  "n_test",
  "poison_rate",
  "trigger_token",
  "target_label",
  "strategies",
  "fuzz_samples_per_strategy",
  "detectors",
  "contamination",
  "seeds",
]);

export function NewExperimentPage() {
  const [config, setConfig] = useState(defaultConfig);
  const [seedText, setSeedText] = useState(config.seeds.join(", "));
  const [currentStep, setCurrentStep] = useState<WizardStep>("Target");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const createExperiment = useCreateExperiment();
  const navigate = useNavigate();

  const currentIndex = WIZARD_STEPS.indexOf(currentStep);
  const units = computeUnits(config);
  const isOverBudget = units > WIZARD_LIMITS.maxComputeUnits;

  function updateConfig<K extends keyof ExperimentConfig>(
    key: K,
    value: ExperimentConfig[K],
  ) {
    setConfig((previous) => ({ ...previous, [key]: value }));
    setFieldErrors((previous) => {
      const next = { ...previous };
      delete next[key];
      return next;
    });
    setRequestError(null);
    createExperiment.reset();
  }

  function numericChange(
    event: ChangeEvent<HTMLInputElement>,
    key: "n_train" | "n_test" | "poison_rate" | "fuzz_samples_per_strategy" | "contamination",
  ) {
    const raw = event.currentTarget.value;
    updateConfig(key, raw === "" ? Number.NaN : Number(raw));
  }

  function nextStep() {
    let nextConfig = config;
    const errors: Record<string, string> = {};
    if (currentStep === "Seeds") {
      const parsed = parseSeeds(seedText);
      if (!parsed.ok) {
        errors.seeds = parsed.error;
      } else {
        nextConfig = { ...config, seeds: parsed.seeds };
      }
    }
    Object.assign(errors, validateStep(currentStep, nextConfig));
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setConfig(nextConfig);
    setCurrentStep(WIZARD_STEPS[currentIndex + 1]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (currentStep !== "Review") {
      nextStep();
      return;
    }

    const allErrors: Record<string, string> = {};
    let submittedConfig = config;
    const parsed = parseSeeds(seedText);
    if (!parsed.ok) {
      allErrors.seeds = parsed.error;
    } else {
      submittedConfig = { ...config, seeds: parsed.seeds };
    }
    for (const step of WIZARD_STEPS.slice(0, -1)) {
      Object.assign(allErrors, validateStep(step, submittedConfig));
    }
    Object.assign(allErrors, validateStep("Review", submittedConfig));
    setFieldErrors(allErrors);
    setRequestError(null);
    if (Object.keys(allErrors).length > 0) return;

    try {
      const created = await createExperiment.mutateAsync(submittedConfig);
      // TODO: redirect to /experiments/:id when the Live Run page is available.
      navigate("/history", {
        state: { createdExperimentId: created.id },
      });
    } catch (error) {
      if (error instanceof ApiError && error.errors?.length) {
        const mapped: Record<string, string> = {};
        for (const item of error.errors) {
          const field = item.field.split(".").at(-1) ?? "";
          if (FIELD_NAMES.has(field)) mapped[field] = item.message;
        }
        setFieldErrors(mapped);
        if (Object.keys(mapped).length === 0) setRequestError(error.detail);
      } else {
        setRequestError(
          error instanceof ApiError
            ? error.detail
            : "The experiment could not be created.",
        );
      }
    }
  }

  function changeSeeds(event: ChangeEvent<HTMLInputElement>) {
    const text = event.currentTarget.value;
    setSeedText(text);
    const parsed = parseSeeds(text);
    if (parsed.ok) updateConfig("seeds", parsed.seeds);
    else {
      setFieldErrors((previous) => {
        const next = { ...previous };
        delete next.seeds;
        return next;
      });
    }
  }

  return (
    <main className="page-layout wizard-page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE / CONFIGURATION</p>
          <h1>New Experiment</h1>
          <p className="panel-copy">
            Configure a toy-model run before submitting it to the runner.
          </p>
        </div>
      </section>

      <ol aria-label="Experiment setup steps" className="wizard-steps">
        {WIZARD_STEPS.map((step, index) => (
          <li
            aria-current={step === currentStep ? "step" : undefined}
            className={step === currentStep ? "wizard-step-current" : ""}
            key={step}
          >
            <span className="wizard-step-number">{index + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>

      <form className="panel wizard-panel" noValidate onSubmit={submit}>
        <div className="wizard-panel-heading">
          <p className="eyebrow">
            STEP {currentIndex + 1} / {WIZARD_STEPS.length}
          </p>
          <h2>{currentStep}</h2>
        </div>

        {currentStep === "Target" && (
          <div className="wizard-fields">
            <Field label="Experiment name" error={fieldErrors.name} id="name">
              <input
                autoComplete="off"
                id="name"
                maxLength={WIZARD_LIMITS.name.max}
                onChange={(event) => updateConfig("name", event.target.value)}
                value={config.name}
              />
            </Field>
            <Field
              label={`Training samples (${WIZARD_LIMITS.n_train.min}–${WIZARD_LIMITS.n_train.max})`}
              error={fieldErrors.n_train}
              id="n_train"
            >
              <input
                id="n_train"
                max={WIZARD_LIMITS.n_train.max}
                min={WIZARD_LIMITS.n_train.min}
                onChange={(event) => numericChange(event, "n_train")}
                type="number"
                value={numericValue(config.n_train)}
              />
            </Field>
            <Field
              label={`Test samples (${WIZARD_LIMITS.n_test.min}–${WIZARD_LIMITS.n_test.max})`}
              error={fieldErrors.n_test}
              id="n_test"
            >
              <input
                id="n_test"
                max={WIZARD_LIMITS.n_test.max}
                min={WIZARD_LIMITS.n_test.min}
                onChange={(event) => numericChange(event, "n_test")}
                type="number"
                value={numericValue(config.n_test)}
              />
            </Field>
            <div className="wizard-field">
              <span className="field-label">Feature source</span>
              <div className="readonly-provenance">
                Fixed for this pipeline <ProvenanceBadge provenance="TOY_MODEL_HIDDEN" />
              </div>
            </div>
          </div>
        )}

        {currentStep === "Attack" && (
          <div className="wizard-fields">
            <Field
              label={`Poison rate (${WIZARD_LIMITS.poison_rate.min}–${WIZARD_LIMITS.poison_rate.max})`}
              error={fieldErrors.poison_rate}
              id="poison_rate"
            >
              <input
                id="poison_rate"
                max={WIZARD_LIMITS.poison_rate.max}
                min={WIZARD_LIMITS.poison_rate.min}
                onChange={(event) => numericChange(event, "poison_rate")}
                step="0.005"
                type="number"
                value={numericValue(config.poison_rate)}
              />
            </Field>
            <Field
              label="Trigger token (2–16 letters, numbers, or underscores)"
              error={fieldErrors.trigger_token}
              id="trigger_token"
            >
              <input
                id="trigger_token"
                maxLength={WIZARD_LIMITS.trigger_token.maxLength}
                onChange={(event) =>
                  updateConfig("trigger_token", event.target.value)
                }
                value={config.trigger_token}
              />
            </Field>
            <fieldset className="wizard-choice-group">
              <legend>Target label</legend>
              {[0, 1].map((label) => (
                <label className="choice-card" key={label}>
                  <input
                    checked={config.target_label === label}
                    name="target_label"
                    onChange={() =>
                      updateConfig("target_label", label as 0 | 1)
                    }
                    type="radio"
                    value={label}
                  />
                  <span>Label {label}</span>
                </label>
              ))}
              {fieldErrors.target_label && (
                <FieldError message={fieldErrors.target_label} />
              )}
            </fieldset>
          </div>
        )}

        {currentStep === "Fuzzing" && (
          <div className="wizard-fields">
            <fieldset className="wizard-choice-group">
              <legend>Mutation strategies</legend>
              <p className="field-hint">
                Choose at least one strategy to evaluate text mutations.
              </p>
              <div className="choice-list">
                {MUTATION_STRATEGIES.map(({ value, description }) => (
                  <label className="choice-card strategy-choice" key={value}>
                    <input
                      checked={config.strategies.includes(value)}
                      onChange={() =>
                        updateConfig(
                          "strategies",
                          toggleSelection(config.strategies, value),
                        )
                      }
                      type="checkbox"
                      value={value}
                    />
                    <span className="choice-description">
                      <strong>{value}</strong>
                      <small>{description}</small>
                    </span>
                  </label>
                ))}
              </div>
              {fieldErrors.strategies && (
                <FieldError message={fieldErrors.strategies} />
              )}
            </fieldset>
            <Field
              label={`Samples per strategy (${WIZARD_LIMITS.fuzz_samples_per_strategy.min}–${WIZARD_LIMITS.fuzz_samples_per_strategy.max})`}
              error={fieldErrors.fuzz_samples_per_strategy}
              id="fuzz_samples_per_strategy"
            >
              <input
                id="fuzz_samples_per_strategy"
                max={WIZARD_LIMITS.fuzz_samples_per_strategy.max}
                min={WIZARD_LIMITS.fuzz_samples_per_strategy.min}
                onChange={(event) =>
                  numericChange(event, "fuzz_samples_per_strategy")
                }
                type="number"
                value={numericValue(config.fuzz_samples_per_strategy)}
              />
            </Field>
          </div>
        )}

        {currentStep === "Detectors" && (
          <div className="wizard-fields">
            <fieldset className="wizard-choice-group">
              <legend>Detectors</legend>
              <div className="choice-list detector-list">
                {DETECTOR_NAMES.map((detector) => (
                  <label className="choice-card" key={detector}>
                    <input
                      checked={config.detectors.includes(detector)}
                      onChange={() =>
                        updateConfig(
                          "detectors",
                          toggleSelection(config.detectors, detector),
                        )
                      }
                      type="checkbox"
                      value={detector}
                    />
                    <span>{detector}</span>
                  </label>
                ))}
              </div>
              {fieldErrors.detectors && (
                <FieldError message={fieldErrors.detectors} />
              )}
            </fieldset>
            <p className="detector-note">
              With 1 detector selected, disagreement is always 0.
            </p>
            <Field
              label={`Contamination (${WIZARD_LIMITS.contamination.min}–${WIZARD_LIMITS.contamination.max})`}
              error={fieldErrors.contamination}
              id="contamination"
            >
              <input
                id="contamination"
                max={WIZARD_LIMITS.contamination.max}
                min={WIZARD_LIMITS.contamination.min}
                onChange={(event) => numericChange(event, "contamination")}
                step="0.01"
                type="number"
                value={numericValue(config.contamination)}
              />
            </Field>
          </div>
        )}

        {currentStep === "Seeds" && (
          <div className="wizard-fields">
            <Field
              label="Seeds (comma-separated integers)"
              error={fieldErrors.seeds}
              hint="Enter 1–20 unique whole numbers from 0 to 2147483647."
              id="seeds"
            >
              <input
                autoComplete="off"
                id="seeds"
                onChange={changeSeeds}
                placeholder="0, 1, 2, 3, 4"
                value={seedText}
              />
            </Field>
          </div>
        )}

        {currentStep === "Review" && (
          <div className="wizard-review">
            <h3>Configuration summary</h3>
            <dl className="config-summary">
              {Object.entries(config).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>
                    {Array.isArray(value) ? value.join(", ") : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="compute-budget">
              <div className="compute-budget-heading">
                <span>Compute units</span>
                <strong>
                  {units.toLocaleString("en-US")} /{" "}
                  {WIZARD_LIMITS.maxComputeUnits.toLocaleString("en-US")}
                </strong>
              </div>
              <div
                aria-label={`${units.toLocaleString("en-US")} of ${WIZARD_LIMITS.maxComputeUnits.toLocaleString("en-US")} compute units`}
                aria-valuemax={WIZARD_LIMITS.maxComputeUnits}
                aria-valuemin={0}
                aria-valuenow={Math.min(units, WIZARD_LIMITS.maxComputeUnits)}
                className={`compute-track${isOverBudget ? " compute-track-over" : ""}`}
                role="progressbar"
              >
                <span
                  style={{
                    width: `${Math.min(
                      100,
                      (units / WIZARD_LIMITS.maxComputeUnits) * 100,
                    )}%`,
                  }}
                />
              </div>
              <p className={isOverBudget ? "field-error" : "field-hint"}>
                {isOverBudget
                  ? `This configuration exceeds the ${WIZARD_LIMITS.maxComputeUnits.toLocaleString("en-US")} unit limit.`
                  : "Seeds × (training + test + strategies × samples per strategy)."}
              </p>
              {fieldErrors.compute_units && (
                <FieldError message={fieldErrors.compute_units} />
              )}
            </div>
            <p className="scope-copy">
              Toy-model results only. Not evidence of production-model backdoor
              detection.
            </p>
          </div>
        )}

        {requestError && (
          <p className="form-error" role="alert">
            {requestError}
          </p>
        )}
        {currentStep === "Review" &&
          Object.entries(fieldErrors)
            .filter(([key]) => FIELD_NAMES.has(key))
            .map(([key, message]) => (
              <p className="field-error" key={key} role="alert">
                {key}: {message}
              </p>
            ))}
        {Object.entries(fieldErrors)
          .filter(([key]) => !FIELD_NAMES.has(key) && key !== "compute_units")
          .map(([key, message]) => (
            <p className="form-error" key={key} role="alert">
              {message}
            </p>
          ))}

        <div className="wizard-actions">
          <button
            className="quiet-button"
            disabled={currentIndex === 0 || createExperiment.isPending}
            onClick={() =>
              setCurrentStep(WIZARD_STEPS[Math.max(0, currentIndex - 1)])
            }
            type="button"
          >
            Back
          </button>
          {currentStep !== "Review" ? (
            <button
              className="primary-button"
              onClick={nextStep}
              type="button"
            >
              Next
            </button>
          ) : (
            <button
              className="primary-button"
              disabled={isOverBudget || createExperiment.isPending}
              type="submit"
            >
              {createExperiment.isPending ? "Submitting…" : "Submit experiment"}
            </button>
          )}
        </div>
      </form>
    </main>
  );
}

interface FieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactElement<InputHTMLAttributes<HTMLInputElement>>;
}

function Field({ id, label, error, hint, children }: FieldProps) {
  const describedBy = [
    hint ? `${id}-hint` : null,
    error ? `${id}-error` : null,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="wizard-field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {cloneElement(children, {
        "aria-describedby": describedBy || undefined,
        "aria-invalid": Boolean(error),
      })}
      {hint && (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
      {error && <FieldError id={`${id}-error`} message={error} />}
    </div>
  );
}

function FieldError({ id, message }: { id?: string; message: string }) {
  return (
    <p className="field-error" id={id} role="alert">
      {message}
    </p>
  );
}

function numericValue(value: number): string | number {
  return Number.isNaN(value) ? "" : value;
}

function toggleSelection<T extends MutationStrategy | DetectorName>(
  values: T[],
  selected: T,
): T[] {
  return values.includes(selected)
    ? values.filter((value) => value !== selected)
    : [...values, selected];
}
