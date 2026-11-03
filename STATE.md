# NeuroFence STATE

## Environment
- OS: Windows (PowerShell)
- Project root: D:\neurofencepro
- Python 3.12.10 (venv at backend\.venv)
- Node v24.13.1, npm 11.8.0, Git 2.53.0, VS Code 1.144.0
- Docker Desktop: not checked yet (needed at Stage 10)
- Installed (pip install -e ".[dev]"): fastapi 0.162.0, pydantic 2.14.2, sqlalchemy 2.1.6,
  scikit-learn 1.9.1, numpy 2.5.4, bcrypt 5.0.0, pyjwt 2.15.1, pytest 9.2.0

## Done
- Stage 0: scaffold, venv, git
- Stage 1: schemas.py + test_schemas.py + docs/api.md (36 passed)
- Stage 2: core/mutations.py + test_mutations.py (47 passed)
- Stage 3: config.py, db/session.py, db/models.py (9 tables), api/health.py, main.py (create_app),
  docs/auth-contract.md, tests (conftest, health, config, db_models). Full suite: 103 passed.
  Real server check: health 200, unknown route 404 problem+json, data/neurofence.db created.
- Stage 4: auth/{passwords,tokens,ratelimit,deps}.py, services/audit.py, api/auth.py, api/audit.py,
  tests (test_auth, test_isolation). Full suite: 125 passed.
  Real server check (port 8010): register (no password in response), login, GET /api/v1/audit
  (register + login.success rows), unauthenticated request -> 401 + WWW-Authenticate: Bearer.
- Stage 5: api/experiments.py (create, list, get, cancel, rerun, delete), tests/test_experiments.py.
  Full suite: 138 passed. Real server check (port 8010): create -> cancel -> rerun -> list -> 401.
- Stage 6a: services/runner.py (stub stages, cooperative cancel, restart recovery, thread pool),
  SSE GET /experiments/{id}/events (replay + Last-Event-ID), tests/test_runner.py.
  Full suite: 152 passed. Real server check (port 8011, isolated temp DB): create -> 16 live SSE
  events -> completed at 100%; cancellation mid-run -> cancelled at 25%.
- Stage 6b: seeded synthetic sentiment dataset, clean and poisoned 16-unit MLPs,
  per-seed clean accuracy and baseline/poisoned ASR in run-local artifacts. Tests verify both
  target labels, deterministic generation, trigger isolation, poisoning, and cancellation between
  seeds. Full suite: 157 passed. Live default config (5 seeds, 1000 train, 400 test) completed
  in 0.336 seconds (server started_at to finished_at).
- Stage 6c: per-seed behavior and deterministic fuzzing results persisted idempotently and
  exposed by authenticated behavior/fuzzing routes. Focused runner/isolation tests: 26 passed;
  full suite: 160 passed. Isolated live-server check: completed run returned 5 behavior and 35
  fuzzing records; 50 samples per fuzz strategy.
- Stage 6d-1: core/{metrics,features,detectors,scoring}.py (pure, no FastAPI) + tests
  (test_metrics golden, test_features, test_detectors, test_scoring). Full suite: 174 passed.
  - Stage 6d-2a: runner wires FEATURES (provenance TOY_MODEL_HIDDEN stored on experiment) and
  DETECTORS (Metric rows per detector x seed, idempotent, cancel-safe). Full suite: 178 passed.
  Live check (port 8010): experiment completed, 15 metric rows.
- Stage 6d-2b: scoring stage persists validated risk scores; authenticated `/metrics` and `/
risk`
  endpoints expose persisted results. `feature_source` restricted to `TOY_MODEL_HIDDEN`.
  Full suite: 182 passed.
- Stage 7: behavior/fuzzing results use `TOY_MODEL_HIDDEN` provenance; scoring explanations
  identify each measurement; public `/meta/limitations` describes fixed design constraints.
  Reproducibility and runner-enabled API smoke tests cover the end-to-end flows.
  Full suite: 185 passed.
  - Stage 8a: frontend scaffold (Vite, React 18, TS strict, Tailwind, TanStack Query, react-router-dom v6
  added), dark theme, API client (problem+json -> ApiError, 401 -> /login), Login/Register,
  protected Overview, RiskBadge, scope footer. `npm run build` green. Verified manually in browser
  through the Vite proxy (/api -> 127.0.0.1:8010). No frontend tests yet.
  - Stage 8b: AppLayout nav, shared ExperimentsTable (status/provenance badges, conditional 2 s polling),
  History (filter, cancel/rerun/delete with ConfirmDialog), Audit log, field-level login errors,
  vitest (6 tests). react-router-dom upgraded to v7; `npm audit --omit=dev` = 0 vulnerabilities.
  Live behaviour verified manually in browser (list, filter, rerun, delete dialog, audit rows).
## Interfaces
- create_app(settings=None) -> FastAPI;
  app.state.{settings, engine, session_factory, login_limiter, dummy_hash, runner}
- get_settings(), Settings (env prefix NEUROFENCE_), APP_VERSION="0.1.0"
- Settings.bcrypt_rounds (default 12, tests use 4)
- Settings.runner_enabled / runner_workers / stub_stage_delay_seconds
- db.session: create_db_engine(url), get_db(request) dependency
- db.models: Base, User, Experiment, ExperimentEvent, Metric, BehaviourResult, FuzzingResult,
  RiskScoreRecord, Report, AuditLog (all except users have user_id)
- main.problem_response(status, detail, errors, instance, headers) -> RFC 9457 JSONResponse
- auth.passwords: hash_password(pw, rounds=12), verify_password(pw, hash)
- auth.tokens: create_access_token(user_id, settings) -> (token, expires_in),
  decode_access_token(token, settings) -> user_id | None
- auth.ratelimit: LoginRateLimiter(max_failures, window_seconds, clock); key = (ip, username)
- auth.deps: get_current_user (use on every protected route), client_ip(request)
- services.audit: record_audit(db, action, user_id=, resource_type=, resource_id=, detail=, ip=)
  (action allow-list in ACTIONS; secrets and non-scalar detail values rejected)
- Routes: POST /api/v1/auth/register, POST /api/v1/auth/login, GET /api/v1/audit,
  POST|GET /api/v1/experiments, GET|DELETE /api/v1/experiments/{id},
  POST /api/v1/experiments/{id}/cancel, POST /api/v1/experiments/{id}/rerun,
  GET /api/v1/experiments/{id}/events (SSE), GET /api/v1/experiments/{id}/behaviour,
  GET /api/v1/experiments/{id}/fuzzing, GET /api/v1/experiments/{id}/metrics,
  GET /api/v1/experiments/{id}/risk, GET /api/v1/meta/limitations (public)
- services.runner: run_experiment, recover_interrupted, ExperimentRunner, STAGE_FUNCS, PIPELINE
- tests/conftest.py fixtures: settings, app, client (temp SQLite per test)
- core.metrics: Counts, Metrics, Summary, confusion_counts(y_true, y_pred), compute_metrics(counts),
  summarize(values) (sample std; None when <2 defined)
- core.features: FeatureSet(train_clean, test_clean, test_triggered, provenance), PROVENANCE,
  hidden_activations(model, matrix), extract_features(model, vectorizer, train_texts, test_texts, trigger)
- core.detectors: DETECTOR_NAMES, run_detectors(features, seed, names=, contamination=0.05) -> DetectorRun,
  vote_stats(run) -> (consensus, disagreement)
- core.scoring: WEIGHTS, band_for(total) -> lowercase band string, score_risk(attack_success_rates=,
  consensus=, fuzz_flip_rates=, disagreement=) -> RiskResult(total, band, components)

## Working commands (D:\neurofencepro\backend, venv active)
- Tests: `.\.venv\Scripts\python.exe -m pytest -q`
- Unused imports: `.\.venv\Scripts\ruff.exe check --select F401 app tests`
- Server: `python -m uvicorn app.main:create_app --factory --port 8010`
  (port 8000 gave WinError 10013 on this machine; use 8010)
- Health: `curl.exe http://127.0.0.1:8010/api/v1/health`
- If port 8010 is busy, an old uvicorn is still running in another terminal.
  Ctrl+C it there (or find it with Get-NetTCPConnection -LocalPort 8010).
   - Frontend dev: `cd frontend; npm run dev` (http://127.0.0.1:5173, proxies /api to 8010; backend must be running)
- Frontend build: `npm run build`
Frontend tests: cd frontend; npm run test
## Notes
- Tables via create_all; Alembic added before Stage 10.
- Starlette warns httpx is deprecated for TestClient (httpx2); harmless, still ignored.
- FastAPI 0.162 wraps included routers in _IncludedRouter objects, so app.routes has no
  per-endpoint APIRoute entries. test_every_protected_route_requires_a_token reads paths from
  app.openapi()["paths"] instead. Routes with include_in_schema=False are NOT covered: do not
  use that flag on protected endpoints, or test them separately.
- test_every_protected_route_requires_a_token now requires >= 12 operations; raise the number as
  protected routes are added. `/api/v1/meta/limitations` is explicitly public.
- Dev DB contains demo_user (id 1) from the real-server demo; registering it again gives 409.
  Delete data/neurofence.db to reset.
- Failed login for an unknown username is audited with user_id NULL and the username is not
  logged. Register has no rate limit (login only).
- Rate limiter is in-memory, single process (document in LIMITATIONS.md).
   - All schema datetimes use UtcDateTime (schemas.py): naive values from SQLite are treated
     as UTC and serialized with a "Z" suffix. Use UtcDateTime for every new *_at field.
     - Experiments of other users return 404 (not 403) on every endpoint, same message as a missing id.
- Cancel allowed from queued/running; rerun from completed/failed/cancelled (else 409).
- Runner: in-process thread pool. Tests set runner_enabled=False in conftest and call
  run_experiment() directly; a separate lifecycle test enables auto-submit. Real stages replace
  STAGE_FUNCS entries.
- Stage 6b dataset and models live only in StageContext.artifacts. Clean-model baseline ASR is
  computed there but not persisted; behavior and fuzzing results are stored and exposed by API.
- Runner status writes are conditional on status == 'running', so cancel/delete are not overwritten.
- Completed experiments persist behavior, fuzzing, detector metrics, and a risk score. Results
  remain toy-model-only; summaries report mean and sample standard deviation over seeds.
- SSE polls the database every 0.5 seconds; use Last-Event-ID to resume a stream.
- Delete removes child rows explicitly (events, metrics, behaviour, fuzzing, risk, reports) so it
  does not depend on SQLite's foreign-key pragma. Audit rows outlive the deleted experiment.
- test_every_protected_route_requires_a_token now requires >= 12 operations; raise the number as
  protected routes are added.
- Dev DB has demo_user plus 2 demo experiments (queued/cancelled) from the Stage 5 demo.
- Detector hyperparameters (IF 100 trees, OCSVM nu=contamination, LOF 20 neighbours) are fixed design
  choices, not tuned on results; detector quality varies by seed.
- With 1 detector selected, disagreement is always 0.
- Fuzzing examples are not persisted; `/metrics` currently returns an empty `fuzz_examples` list.
- Risk weights are design choices, not a validated standard.
- Detectors are fit on the clean train texts of the poisoned model; eval = test clean (label 0) +
  same test texts with trigger appended (label 1).s

## Known issues
   - None.
## Next
-Stage 8c: New Experiment wizard (6 steps) + Quickstart demo.