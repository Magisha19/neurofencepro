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
- Stage 0: folder scaffold, .gitignore, backend venv, git repo (origin/main)
- Stage 1: backend/app/schemas.py, backend/tests/test_schemas.py, docs/api.md
  (36 tests passed, real output pasted)

## Interfaces (schemas.py)
- Constants: SCOPE_STATEMENT, RISK_SCORE_LABEL, SCORE_WEIGHTS, MAX_COMPUTE_UNITS=120000
- Enums: Provenance, MutationStrategy, DetectorName, ExperimentStatus, Stage, RiskBand, ReportFormat
- band_for_score(score) -> RiskBand
- ExperimentConfig (+ .compute_units, .config_hash()), ExperimentCreate = ExperimentConfig
- Metrics: ConfusionCounts, ClassificationMetrics, MetricSummary, DetectorSeedResult,
  DetectorSummary, BehaviourSeedResult, BehaviourSummary, FuzzingSeedResult,
  FuzzingSummary, FuzzExample, MetricsResponse
- Risk: ScoreComponent, RiskScore, RiskResponse
- Experiments: ExperimentOut, ExperimentList, ExperimentEvent
- Auth: RegisterRequest, LoginRequest, TokenResponse, UserPublic
- Others: ReportOut, AuditLogOut, AuditLogList, HealthResponse, LimitationsResponse,
  ProblemDetail, ProblemFieldError
- Rules enforced: scope statement fixed, ratio null iff denominator zero,
  std = sample std (ddof=1), TRANSFORMER_HIDDEN not selectable yet

## Working commands (run in D:\neurofencepro\backend with venv active)
- Activate: `.\.venv\Scripts\Activate.ps1`
- Tests: `python -m pytest -v`
- Import check: `python -c "from app.schemas import ExperimentConfig; c=ExperimentConfig(); print(c.compute_units, c.config_hash()[:12])"`
  -> `8750 b1e0aed4e0e3`

## Notes
- Existing README.md (15 bytes) will be rewritten in Stage 10.
- Default seeds [0,1,2,3,4]; at least 1 mutation strategy required.

## Next
- Stage 2: core/mutations.py (7 strategies, pure, seedable via
  random.Random(f"neurofence:{strategy}:{seed}:{index}")) + tests/test_mutations.py