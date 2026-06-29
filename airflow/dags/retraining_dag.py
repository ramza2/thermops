"""DAG: 승인된 재학습 후보 기반 모델 재학습."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import RETRAINING_DEFAULT_ARGS
from pipeline_tasks import finalize_retraining_candidate, run_retraining, validate_retraining_candidate

with DAG(
    dag_id="retraining_dag",
    default_args=RETRAINING_DEFAULT_ARGS,
    description="승인된 재학습 후보 기반 모델 재학습 (conf.candidate_id 필수)",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "retraining"],
) as dag:
    validate = PythonOperator(task_id="validate_candidate", python_callable=validate_retraining_candidate)
    train = PythonOperator(task_id="run_retraining", python_callable=run_retraining)
    finalize = PythonOperator(task_id="finalize_candidate", python_callable=finalize_retraining_candidate)

    validate >> train >> finalize
