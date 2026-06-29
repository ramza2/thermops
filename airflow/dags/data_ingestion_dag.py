"""DAG-001: 데이터 적재."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_ingestion

with DAG(
    dag_id="data_ingestion_dag",
    default_args=DEFAULT_ARGS,
    description="CSV/DB 데이터 적재",
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "ingestion"],
) as dag:
    PythonOperator(task_id="run_ingestion", python_callable=run_ingestion)
