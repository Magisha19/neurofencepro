# NeuroFence API contract (draft, Stage 1)

Base path: `/api/v1`. Schemas live in `backend/app/schemas.py` (single source of truth).
Errors: RFC 9457 `application/problem+json` (`ProblemDetail`). No stack traces. Validation
errors list `field` and `message` only, never the submitted value.

Every result payload carries `scope_statement`:
"Toy-model results only. Not evidence of production-model backdoor detection."
Result payloads also carry `provenance` (SIMULATED | TOY_MODEL_HIDDEN | TRANSFORMER_HIDDEN).
The risk score is labelled "Risk indicators observed in this experiment". No endpoint says a model is "safe".

## Endpoints

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | /health | no | - | HealthResponse |
| POST | /auth/register | no | RegisterRequest | UserPublic (201) |
| POST | /auth/login | no | LoginRequest | TokenResponse |
| POST | /experiments | yes | ExperimentCreate | ExperimentOut (201) |
| GET | /experiments | yes | ?limit&offset | ExperimentList |
| GET | /experiments/{id} | yes | - | ExperimentOut |
| GET | /experiments/{id}/events | yes | - | SSE stream of ExperimentEvent |
| GET | /experiments/{id}/behaviour | yes | - | BehaviourResultsResponse |
| GET | /experiments/{id}/fuzzing | yes | - | FuzzingResultsResponse |
| GET | /experiments/{id}/metrics | yes | - | MetricsResponse |
| GET | /experiments/{id}/risk | yes | - | RiskResponse |
| POST | /experiments/{id}/cancel | yes | - | ExperimentOut |
| POST | /experiments/{id}/rerun | yes | - | ExperimentOut (201) |
| DELETE | /experiments/{id} | yes | - | 204 |
| POST | /experiments/{id}/reports?format=pdf\|md | yes | - | ReportOut (201) |
| GET | /reports/{id}/download | yes | - | file |
| GET | /audit | yes | ?limit&offset | AuditLogList |
| GET | /meta/limitations | no | - | LimitationsResponse |

Another user's resource returns **404**, never 403.

## ExperimentConfig limits

| Field | Rule | Default |
|---|---|---|
| name | 1-80 chars | "NeuroFence experiment" |
| seeds | 1-20 unique ints, 0 to 2147483647 | [0,1,2,3,4] |
| poison_rate | 0.005 - 0.30 | 0.05 |
| trigger_token | 2-16 chars of A-Z a-z 0-9 _ | cf_zq7 |
| target_label | 0 or 1 | 1 |
| n_train | 200 - 5000 | 1000 |
| n_test | 100 - 2000 | 400 |
| strategies | 1-7 unique | all 7 |
| fuzz_samples_per_strategy | 10 - 200 | 50 |
| detectors | 1-3 unique | all 3 |
| contamination | 0.01 - 0.30 | 0.05 |
| feature_source | TOY_MODEL_HIDDEN only | TOY_MODEL_HIDDEN |

Compute budget: `seeds * (n_train + n_test + strategies * fuzz_samples) <= 120000`.
Unknown fields are rejected. Fuzzing runs only against NeuroFence's own toy model.

Behavior results evaluate the poisoned toy model on the clean test set and on test samples
with the configured trigger. Attack success rate is measured over non-target labels;
label-flip rate counts predictions changed by adding the trigger. Fuzzing flip rate counts
predictions changed by each deterministic mutation, compared with the same model's prediction
on the original text. Result endpoints include scope and provenance and return 404 for another
user's experiment. The `/metrics` and `/risk` endpoints return 409 with "Results not available
yet" until their persisted results exist.

## Metrics rules

- A ratio with a zero denominator is `null`, never 0. F1 = 2TP / (2TP + FP + FN).
- Summaries are mean ± std over seeds. std is sample std (ddof=1), null with fewer than 2 values.
- `n_defined` / `n_total` shows how many seeds defined the metric.

## Risk score

Total 0-100 = behavioural_divergence (40) + detector_consensus (30) + fuzzing_fragility (20)
+ detector_disagreement (10). Bands: low 0-24, moderate 25-49, high 50-74, critical 75-100.
Weights are design choices, not a validated standard. Headline detector, behavior, and fuzzing
summaries are mean ± sample standard deviation over seeds; they do not select a best run.

## Auth

Username 3-32 chars (letters, digits, `_ . -`, stored lowercase). Password 12-128 chars and
at most 72 bytes (bcrypt limit). Responses never contain password data.