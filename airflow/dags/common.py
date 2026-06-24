"""공통 DAG 유틸."""
from datetime import datetime, timedelta

DEFAULT_ARGS = {
    "owner": "thermops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


def log_pipeline_run(pipeline_type: str, pipeline_id: str, status: str, message: str = ""):
  """파이프라인 실행 이력 기록 (템플릿)."""
  print(f"[{pipeline_type}] {pipeline_id} -> {status}: {message}")
