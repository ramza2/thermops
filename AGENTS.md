# AGENTS.md

## Cursor Cloud specific instructions

THERMOps is a multi-service district-heating heat-demand MLOps platform. The documented workflow uses Docker Compose, but **Docker is not available in the Cursor Cloud VM**. Instead, the core stack runs natively: **PostgreSQL 16 (system package) + FastAPI backend + Vite frontend**. This is enough to boot the app and exercise its core functionality (dashboard, data/feature/model/prediction management APIs and UI). See `README.md` section "로컬 개발 (Docker 없이)" for the canonical local-dev commands.

### Services and how to run them (dev mode)

| Service | Port | Start command | Notes |
|---------|------|---------------|-------|
| PostgreSQL 16 | 5432 | `sudo pg_ctlcluster 16 main start` | Not auto-started on boot; run this once per session. Role/DBs `thermops` + `thermops_airflow` and the schema/seed already exist in the VM snapshot. |
| Backend (FastAPI) | 8000 | `cd backend && GIT_PYTHON_REFRESH=quiet ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | Uses venv at `backend/.venv`. Reads `backend/.env`. Swagger at `/docs`, health at `/health`. |
| Frontend (Vite) | 5173 | `cd frontend && npm run dev -- --host 0.0.0.0` | Reads `frontend/.env.local`. |

Run long-lived services in tmux (`tmux -f /exec-daemon/tmux.portal.conf`).

### Non-obvious gotchas

- **`GIT_PYTHON_REFRESH` must be an OS env var, not in `backend/.env`.** The pydantic `Settings` model uses `extra=forbid`, so putting unknown keys (like `GIT_PYTHON_REFRESH`) in `backend/.env` crashes startup with `extra_forbidden`. Only real setting fields belong in `backend/.env`; pass `GIT_PYTHON_REFRESH=quiet` on the command line (mlflow/GitPython needs it).
- **Frontend defaults to VIEWER role.** Without `VITE_USER_ROLE=ADMIN` (set in `frontend/.env.local`), the UI mounts as VIEWER and create/edit buttons are hidden. `VITE_USER_ROLE` is a frontend-only mock; there is no real auth.
- **`backend/.env` and `frontend/.env.local`** are git-ignored/untracked and point the backend at `localhost:5432` (the compose files use hostname `postgres`). Recreate them if missing.
- **Clean DB seed only.** `db/init/02_seed_clean.sql` seeds only common-codes/system-config — no business data. Sites, datasets, features, models, etc. are created via the UI/API. To (re)apply schema+seed to a fresh DB: `PGPASSWORD=thermops psql -h localhost -U thermops -d thermops -f db/init/01_schema.sql` then `... -f db/init/02_seed_clean.sql`.

### Optional services (require Docker — unavailable here)

MLflow (5000), MinIO (9000/9001), and Airflow (8080) are only wired up through Docker Compose. Model training / batch prediction / drift / orchestration end-to-end flows depend on them and cannot be exercised natively without installing Docker. The backend, data management, feature management, and all read/CRUD APIs work without them.

### Tests / build

- API smoke test (backend must be running): `python3 scripts/smoke_test_api.py`
- Full regression runner: `python3 scripts/run_regression_tests.py --group quick` (needs running services)
- Frontend typecheck + build: `cd frontend && npm run build` (no separate lint script exists)
