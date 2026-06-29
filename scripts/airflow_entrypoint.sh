#!/bin/bash
set -e

echo "[airflow] DB migrate..."
for i in 1 2 3 4 5; do
  if airflow db migrate; then
    break
  fi
  echo "[airflow] migrate retry $i/5..."
  sleep 3
done

airflow users create \
  --username "${AIRFLOW_USERNAME:-admin}" \
  --password "${AIRFLOW_PASSWORD:-admin}" \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@thermops.local 2>/dev/null || true

echo "[airflow] starting webserver and scheduler..."
airflow webserver &
exec airflow scheduler
