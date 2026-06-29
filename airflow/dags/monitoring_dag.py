"""DAG-008: 모니터링."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_monitoring

with DAG(
    dag_id="monitoring_dag",
    default_args=DEFAULT_ARGS,
    description="예측-실제 매칭 및 성능 평가",
    schedule="0 8 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "monitoring"],
) as dag:
    PythonOperator(task_id="run_monitoring", python_callable=run_monitoring)
