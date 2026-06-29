"""DAG: Drift 감지."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_drift_detection

with DAG(
    dag_id="drift_detection_dag",
    default_args=DEFAULT_ARGS,
    description="Drift 감지 및 재학습 후보 자동 생성",
    schedule="0 9 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "drift"],
) as dag:
    PythonOperator(task_id="run_drift_detection", python_callable=run_drift_detection)
