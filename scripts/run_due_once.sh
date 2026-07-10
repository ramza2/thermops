#!/usr/bin/env sh
# R10-S10: cron/외부 스케줄러에서 run-due worker 1회 실행 예시 (OS cron 자동 등록 없음)
# 사용 예:
#   ./scripts/run_due_once.sh
# crontab 예시 (문서용):
#   * * * * * cd /opt/thermops && ./scripts/run_due_once.sh >> /var/log/thermops-run-due.log 2>&1

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env.deploy ]; then
  COMPOSE_FILE="docker-compose.traefik.yml"
  ENV_FILE=".env.deploy"
elif [ -f docker-compose.yml ]; then
  COMPOSE_FILE="docker-compose.yml"
  ENV_FILE=".env"
else
  echo "compose file not found" >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" ${ENV_FILE:+--env-file "$ENV_FILE"} run --rm run-due-worker \
  python -m app.workers.run_due_worker --mode once
