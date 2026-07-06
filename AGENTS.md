# AGENTS.md

## Cursor Cloud specific instructions

> **Scope:** This section is for the **Cursor Cloud VM** (no Docker). For **local Windows/macOS with Docker Compose** (regression, MLflow, Airflow, Traefik), follow `README.md` first.

THERMOps is a multi-service district-heating heat-demand MLOps platform. The documented workflow uses Docker Compose, but **Docker is not available in the Cursor Cloud VM**. Instead, the core stack runs natively: **PostgreSQL 15+ (system package; Cloud snapshot uses 16) + FastAPI backend + Vite frontend**. This is enough to boot the app and exercise core functionality (dashboard, data/feature/model/prediction management APIs and UI). See `README.md` section "로컬 개발 (Docker 없이)" for general native-dev notes; this file adds Cloud-specific commands.

### Services and how to run them (dev mode)

| Service | Port | Start command | Notes |
|---------|------|---------------|-------|
| PostgreSQL | 5432 | `sudo pg_ctlcluster 16 main start` | Not auto-started on boot; run once per session. In the Cloud VM snapshot, role/DBs `thermops` + `thermops_airflow` and schema/seed may already exist. |
| Backend (FastAPI) | 8000 | `cd backend && GIT_PYTHON_REFRESH=quiet ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | venv at `backend/.venv`. Env: `backend/.env` or repo-root `.env` (see below). Swagger `/docs`, health `/health`. |
| Frontend (Vite) | 5173 | `cd frontend && npm run dev -- --host 0.0.0.0` | Env: `frontend/.env.local` or repo-root `.env` (`VITE_*`). |

Run long-lived services in tmux (`tmux -f /exec-daemon/tmux.portal.conf`).

### Environment files

- Copy repo-root `.env.example` → `.env` (git-ignored). For backend started from `backend/`, you may also use `backend/.env` with the same `POSTGRES_*` / `DATABASE_URL` values pointing at `localhost:5432` (Compose uses hostname `postgres`).
- Frontend: set `VITE_API_BASE_URL=http://localhost:8000/api/v1` and **`VITE_USER_ROLE=ADMIN`** in `.env` or `frontend/.env.local`.

### DB schema, seed, and migrations

- **Clean seed only:** `db/init/02_seed_clean.sql` — common-codes/system-config only; no business data (data sources, datasets, models, etc. start at 0).
- **Fresh DB (full init):**
  ```bash
  PGPASSWORD=thermops psql -h localhost -U thermops -d thermops -f db/init/01_schema.sql
  PGPASSWORD=thermops psql -h localhost -U thermops -d thermops -f db/init/02_seed_clean.sql
  ```
- **Existing DB after pulling new commits:** apply incremental migrations (required for R10+ API connector tables, etc.):
  ```bash
  python3 scripts/apply_dev_migrations.py
  ```

### Non-obvious gotchas

- **`GIT_PYTHON_REFRESH`:** Prefer an **OS/shell env var** (e.g. prefix the uvicorn command with `GIT_PYTHON_REFRESH=quiet`). Do not treat it as a backend Settings field. Docker Compose sets it for the backend container; native runs may need it when MLflow/GitPython paths are touched.
- **Frontend defaults to VIEWER role.** Without `VITE_USER_ROLE=ADMIN`, the UI mounts as VIEWER and create/edit buttons are hidden. Mock only — no real auth.
- **Phase work (R10+, model regression):** Needs Docker stack (postgres + backend + mlflow + airflow). Cloud native mode is suitable for smoke tests and CRUD/UI checks, not full `run_regression_tests.py --group model`.

### Optional services (require Docker — unavailable in Cloud VM)

MLflow (5000), MinIO (9000/9001), and Airflow (8080) are wired through Docker Compose only. Model training, batch prediction, drift, and orchestration E2E depend on them. Backend CRUD and data-management APIs work without them.

### Tests / build

- API smoke test (backend running): `python3 scripts/smoke_test_api.py`
- Quick regression (backend + postgres running): `python3 scripts/run_regression_tests.py --group quick`
- Model/full regression: Docker Compose recommended — see `README.md`
- Frontend typecheck + build: `cd frontend && npm run build` (no separate lint script)
