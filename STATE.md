# NeuroFence STATE

## Environment
- OS: Windows (PowerShell)
- Project root: D:\neurofencepro
- Python 3.12.10 (venv at backend\.venv)
- Node v24.13.1, npm 11.8.0, Git 2.53.0, VS Code 1.144.0
- Docker Desktop: not checked yet (needed at Stage 10)

## Done
- Stage 0: folder scaffold, .gitignore, backend venv, git repo (origin/main)

## Working commands
- Activate venv: `cd D:\neurofencepro\backend; .\.venv\Scripts\Activate.ps1`
- Check versions: `py -3.12 --version`

## Notes
- pip 26.3 in venv. An interrupted pip upgrade left a `~ip` folder; it was removed.
- Existing README.md (15 bytes) will be rewritten in Stage 10.

## Next
- Stage 1: schemas.py (Pydantic v2 contracts with honesty fields) + docs/api.md