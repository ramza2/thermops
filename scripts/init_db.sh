#!/usr/bin/env bash
# THERMOps DB 초기화 스크립트 (로컬 PostgreSQL)
set -e
PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PGUSER=${PGUSER:-thermops}
PGDATABASE=${PGDATABASE:-thermops}

echo "Applying schema..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f db/init/01_schema.sql
echo "Applying seed data..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f db/init/02_seed_clean.sql
echo "Done."
