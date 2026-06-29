"""DAG-006: 모델 학습."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import run_model_training

with DAG(
    dag_id="model_training_dag",
    default_args=DEFAULT_ARGS,
    description="모델 학습 및 MLflow 등록",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "training"],
) as dag:
    PythonOperator(task_id="run_model_training", python_callable=run_model_training)
