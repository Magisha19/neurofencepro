# NeuroFence architecture

## Scope and provenance

NeuroFence currently runs deterministic synthetic sentiment data through its own
16-unit MLP. Results are toy-model observations only and are not claims about
production models. Feature extraction uses the poisoned toy model's hidden
activations and records `TOY_MODEL_HIDDEN` provenance. Configurations requesting
other feature sources are rejected.

## Experiment pipeline

The in-process runner executes these stages in order:

1. `dataset`: create seeded synthetic training and test samples.
2. `train_clean`: fit a clean 16-unit MLP.
3. `plant_backdoor`: poison selected training samples and fit the poisoned MLP.
4. `behaviour`: persist per-seed behavior measurements.
5. `fuzzing`: persist per-seed, per-strategy prediction-flip measurements.
6. `features`: extract hidden activations from the poisoned MLP.
7. `detectors`: fit the configured anomaly detectors and persist per-seed metrics.
8. `scoring`: combine behavior, detector-vote, and fuzzing inputs into a persisted
   risk-indicator score.

The runner uses a configurable Python thread pool in the API process. Cancellation
is cooperative between computational units; restarting the server marks interrupted
running experiments as failed and resubmits queued experiments.

## Persistence and API

SQLite stores users, experiment configuration and status, event history, behavior
and fuzzing results, detector metric rows, risk-score components and weights, and
audit history. Trained models, datasets, and intermediate feature artifacts are
kept in memory for the duration of a run.

Authenticated experiment endpoints enforce ownership and return the same not-found
response for unknown and other users' experiment IDs. `/api/v1/meta/limitations` is
public and returns a code-defined list of current design constraints. Metrics
summaries use per-seed means and sample standard deviations; the configured score
weights are design choices, not a validated standard.