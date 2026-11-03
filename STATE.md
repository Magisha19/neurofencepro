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
- Stage 1: backend/app/schemas.py, backend/tests/test_schemas.py, docs/api.md (36 passed)
- Stage 2: backend/app/core/mutations.py, backend/tests/test_mutations.py
  (47 passed; full suite 83 passed, real output pasted)

## Interfaces (core/mutations.py)
- mutate(text, strategy, seed, index=0) -> str   (pure, deterministic; ValueError/TypeError on bad input)
- make_rng(strategy, seed, index) -> random.Random(f"neurofence:{strategy}:{seed}:{index}")
- display_hidden(text) -> str   (invisible chars shown as <U+XXXX>)
- make_fuzz_example(text, strategy, seed, index=0) -> FuzzExample
- Tables: HOMOGLYPHS, LEET, ZERO_WIDTH_CHARS, SYNONYMS (24 words), INJECTIONS (4 harmless markers)
- MAX_TEXT_LEN = 2000

## Working commands (run in D:\neurofencepro\backend, venv active)
- All tests: `python -m pytest -q`  -> 83 passed
- Commit/push only from D:\neurofencepro (root)

## Notes
- Stage 5 dataset vocabulary must overlap SYNONYMS keys, otherwise synonym_swap changes nothing.
- instruction_injection uses harmless synthetic markers only (fuzzing targets our own toy model).
- Lesson: check the prompt shows D:\neurofencepro\backend> before creating files; verify file Length after paste.

## Next
- Stage 3: auth contract, config.py, DB models, main.py, GET /api/v1/health