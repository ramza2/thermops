#!/usr/bin/env python3
"""THERMOps clean deployment — 결과성 데이터만 초기화.

마스터·템플릿(지사, Feature, Feature Set, Training Config, CSV 소스 등록)은 유지하고
적재·학습·예측·Drift·파이프라인 이력 등 결과 테이블만 TRUNCATE 합니다.

사용 예:
  THERMOPS_DEPLOY_ENV=clean python scripts/reset_clean_deploy.py --yes

주의: 운영 DB에서 실행하지 마세요. --yes 없이는 실행되지 않습니다.
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    import psycopg2
except ImportError:
    print("psycopg2가 필요합니다: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

# FK 의존 순서: 자식 → 부모
RESULT_TABLES: list[str] = [
    "tb_prediction_actual_match",
    "tb_heat_demand_prediction",
    "tb_prediction_job",
    "tb_model_performance_metric",
    "tb_drift_report",
    "tb_retraining_candidate",
    "tb_pipeline_run",
    "tb_training_job",
    "tb_model_version",
    "tb_model_experiment",
    "tb_feature_lineage",
    "tb_feature_dataset",
    "tb_dataset_version",
    "tb_data_quality_run",
    "tb_heat_demand_actual",
    "tb_weather_observation",
]


def parse_database_url(url: str) -> dict[str, str]:
    """postgresql+asyncpg://user:pass@host:port/db → psycopg2 kwargs."""
    raw = url.replace("postgresql+asyncpg://", "postgresql://")
    if not raw.startswith("postgresql://"):
        raise ValueError(f"지원하지 않는 DATABASE_URL: {url}")
    from urllib.parse import urlparse

    p = urlparse(raw)
    return {
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "dbname": (p.path or "/thermops").lstrip("/"),
        "user": p.username or "thermops",
        "password": p.password or "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="THERMOps 결과성 테이블 TRUNCATE (clean reset)")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="확인 없이 실행 (필수)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql+asyncpg://thermops:thermops@localhost:5432/thermops"),
        help="대상 DB URL (기본: DATABASE_URL 환경 변수)",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="THERMOPS_DEPLOY_ENV=clean 검사 생략 (로컬 개발용)",
    )
    args = parser.parse_args()

    if not args.yes:
        print("오동작 방지: --yes 옵션을 명시해야 실행됩니다.", file=sys.stderr)
        return 1

    deploy_env = os.environ.get("THERMOPS_DEPLOY_ENV", "")
    if not args.skip_env_check and deploy_env != "clean":
        print(
            "THERMOPS_DEPLOY_ENV=clean 이 설정되지 않았습니다.\n"
            "  export THERMOPS_DEPLOY_ENV=clean\n"
            "또는 --skip-env-check (로컬 개발만)",
            file=sys.stderr,
        )
        return 1

    try:
        conn_info = parse_database_url(args.database_url)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print("=== THERMOps Clean Reset ===")
    print(f"  host:     {conn_info['host']}:{conn_info['port']}")
    print(f"  database: {conn_info['dbname']}")
    print(f"  user:     {conn_info['user']}")
    print(f"  tables:   {len(RESULT_TABLES)}개 TRUNCATE")
    print()
    print("유지: tb_site, tb_feature, tb_feature_set, tb_training_config, tb_data_source(등록), tb_system_config ...")
    print("삭제: 적재·Feature 결과·학습·예측·Drift·파이프라인 이력")
    print()

    try:
        conn = psycopg2.connect(**conn_info)
        conn.autocommit = False
        with conn.cursor() as cur:
            for table in RESULT_TABLES:
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
            conn.commit()
        conn.close()
    except psycopg2.Error as exc:
        print(f"DB 오류: {exc}", file=sys.stderr)
        return 1

    print("TRUNCATE 완료.")
    print()
    print("추가 초기화 (선택, Docker 환경):")
    print("  # Airflow DAG run 이력")
    print("  docker compose -f docker-compose.traefik.yml exec airflow airflow db clean --yes")
    print("  # MinIO MLflow 버킷 (볼륨 삭제가 가장 확실)")
    print("  docker compose -f docker-compose.traefik.yml down -v  # 전체 volume 삭제 시")
    print("  # MLflow experiment/run은 DB thermops 내 mlflow 테이블 또는 UI에서 정리")
    return 0


if __name__ == "__main__":
    sys.exit(main())
