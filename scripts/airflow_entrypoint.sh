#!/bin/bash
set -e

# POSTGRES_PASSWORD 특수문자(@ 등) URL 인코딩 — compose 인라인 URL 조합 시 파싱 깨짐 방지
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="$(python3 -c "
from urllib.parse import quote_plus
import os
u = quote_plus(os.environ.get('POSTGRES_USER', 'thermops'))
p = quote_plus(os.environ.get('POSTGRES_PASSWORD', 'thermops'))
print(f'postgresql+psycopg2://{u}:{p}@postgres:5432/thermops_airflow')
")"
export THERMOps_DB_URL="$(python3 -c "
from urllib.parse import quote_plus
import os
u = quote_plus(os.environ.get('POSTGRES_USER', 'thermops'))
p = quote_plus(os.environ.get('POSTGRES_PASSWORD', 'thermops'))
db = os.environ.get('POSTGRES_DB', 'thermops')
print(f'postgresql://{u}:{p}@postgres:5432/{db}')
")"

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
