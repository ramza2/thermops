"""DAG-007: 배치 예측."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_batch_prediction

with DAG(
    dag_id="batch_prediction_dag",
    default_args=DEFAULT_ARGS,
    description="배치 예측 실행",
    schedule="0 5 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "prediction"],
) as dag:
    PythonOperator(task_id="run_batch_prediction", python_callable=run_batch_prediction)
