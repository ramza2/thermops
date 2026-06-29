"""전체 THERMOps 파이프라인."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS
from pipeline_tasks import (
    mark_pipeline_running,
    run_batch_prediction,
    run_feature_build,
    run_ingestion,
    run_model_training,
    run_monitoring,
    run_quality_check,
)

with DAG(
    dag_id="thermops_full_pipeline_dag",
    default_args=DEFAULT_ARGS,
    description="THERMOps 전체 파이프라인",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "full"],
) as dag:
    t_start = PythonOperator(task_id="mark_running", python_callable=mark_pipeline_running)
    t_ingest = PythonOperator(task_id="data_ingestion", python_callable=run_ingestion)
    t_quality = PythonOperator(task_id="data_quality", python_callable=run_quality_check)
    t_feature = PythonOperator(task_id="feature_build", python_callable=run_feature_build)
    t_train = PythonOperator(task_id="model_training", python_callable=run_model_training)
    t_predict = PythonOperator(task_id="batch_prediction", python_callable=run_batch_prediction)
    t_eval = PythonOperator(task_id="prediction_evaluation", python_callable=run_monitoring)

    t_start >> t_ingest >> t_quality >> t_feature >> t_train >> t_predict >> t_eval
