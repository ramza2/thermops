#!/usr/bin/env python3
"""개발용 DB 스키마 보완 (기존 볼륨 마이그레이션)."""

from __future__ import annotations

import os
import subprocess
import sys

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

MIGRATIONS = [
    (
        "tb_pipeline_run.result_summary",
        "ALTER TABLE tb_pipeline_run ADD COLUMN IF NOT EXISTS result_summary JSONB;",
    ),
]


def run_sql(sql: str) -> None:
    if os.environ.get("THERMOOPS_USE_DOCKER", "1") == "1":
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2 required when THERMOOPS_USE_DOCKER=0") from exc
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    print("THERMOps dev migrations")
    try:
        for label, sql in MIGRATIONS:
            print(f"  [apply] {label}")
            run_sql(sql)
        print("PASSED")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"FAILED: {exc.stderr or exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
