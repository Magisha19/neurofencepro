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

## Interfaces
- create_app(settings=None) -> FastAPI;
  app.state.{settings, engine, session_factory, login_limiter, dummy_hash}
- get_settings(), Settings (env prefix NEUROFENCE_), APP_VERSION="0.1.0"
- Settings.bcrypt_rounds (default 12, tests use 4)
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
-- Routes: POST /api/v1/auth/register, POST /api/v1/auth/login, GET /api/v1/audit,
  POST|GET /api/v1/experiments, GET|DELETE /api/v1/experiments/{id},
  POST /api/v1/experiments/{id}/cancel, POST /api/v1/experiments/{id}/rerun
- tests/conftest.py fixtures: settings, app, client (temp SQLite per test)

## Working commands (D:\neurofencepro\backend, venv active)
- Tests: `python -m pytest -q`  -> 125 passed
- Server: `python -m uvicorn app.main:create_app --factory --port 8010`
  (port 8000 gave WinError 10013 on this machine; use 8010)
- Health: `curl.exe http://127.0.0.1:8010/api/v1/health`
- If port 8010 is busy, an old uvicorn is still running in another terminal.
  Ctrl+C it there (or find it with Get-NetTCPConnection -LocalPort 8010).

## Notes
- Tables via create_all; Alembic added before Stage 10.
- Starlette warns httpx is deprecated for TestClient (httpx2); harmless, still ignored.
- FastAPI 0.162 wraps included routers in _IncludedRouter objects, so app.routes has no
  per-endpoint APIRoute entries. test_every_protected_route_requires_a_token reads paths from
  app.openapi()["paths"] instead. Routes with include_in_schema=False are NOT covered: do not
  use that flag on protected endpoints, or test them separately.
- When new routers land (experiments, reports), raise the `checked >= 1` guard in that test
  to the expected route count.
- Dev DB contains demo_user (id 1) from the real-server demo; registering it again gives 409.
  Delete data/neurofence.db to reset.
- Failed login for an unknown username is audited with user_id NULL and the username is not
  logged. Register has no rate limit (login only).
- Rate limiter is in-memory, single process (document in LIMITATIONS.md).
   - All schema datetimes use UtcDateTime (schemas.py): naive values from SQLite are treated
     as UTC and serialized with a "Z" suffix. Use UtcDateTime for every new *_at field.
     - Experiments of other users return 404 (not 403) on every endpoint, same message as a missing id.
- Cancel allowed from queued/running; rerun from completed/failed/cancelled (else 409).
  Cancel currently only flips the status. When the pipeline runner exists (Stage 6), a running
  worker must check for cancellation between stages.
- Delete removes child rows explicitly (events, metrics, behaviour, fuzzing, risk, reports) so it
  does not depend on SQLite's foreign-key pragma. Audit rows outlive the deleted experiment.
- test_every_protected_route_requires_a_token now requires >= 7 operations; raise the number as
  routers are added.
- Dev DB has demo_user plus 2 demo experiments (queued/cancelled) from the Stage 5 demo.

## Known issues
   - None.
## Next
- Decide Stage 6 scope: pipeline runner (background execution, events, progress, cooperative cancel).
- Still assumed: SSE via fetch stream + Authorization header (no token in query string).t.