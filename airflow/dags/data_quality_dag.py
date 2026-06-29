"""DAG: 데이터 품질 점검."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_quality_check

with DAG(
    dag_id="data_quality_dag",
    default_args=DEFAULT_ARGS,
    description="데이터 품질 점검",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "quality"],
) as dag:
    PythonOperator(task_id="run_quality_check", python_callable=run_quality_check)
