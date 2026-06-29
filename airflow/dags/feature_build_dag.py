"""DAG-005: Feature 생성."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_feature_build

with DAG(
    dag_id="feature_build_dag",
    default_args=DEFAULT_ARGS,
    description="학습/예측 공통 Feature 생성",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "feature"],
) as dag:
    PythonOperator(task_id="run_feature_build", python_callable=run_feature_build)
