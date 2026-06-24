"""DAG-006: 모델 학습 파이프라인 템플릿."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, log_pipeline_run


def prepare_dataset(**context):
    log_pipeline_run("TRAINING", "model_training_dag", "RUNNING", "학습 데이터셋 준비")


def train_baseline(**context):
    log_pipeline_run("TRAINING", "model_training_dag", "RUNNING", "Baseline 학습")


def train_ml_model(**context):
    log_pipeline_run("TRAINING", "model_training_dag", "RUNNING", "LightGBM/XGBoost 학습")


def evaluate_and_log(**context):
    log_pipeline_run("TRAINING", "model_training_dag", "SUCCESS", "MLflow 기록 완료")


with DAG(
    dag_id="model_training_dag",
    default_args=DEFAULT_ARGS,
    description="Baseline/ML 모델 학습 및 MLflow 기록",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "training"],
) as dag:
    t1 = PythonOperator(task_id="prepare_dataset", python_callable=prepare_dataset)
    t2 = PythonOperator(task_id="train_baseline", python_callable=train_baseline)
    t3 = PythonOperator(task_id="train_ml_model", python_callable=train_ml_model)
    t4 = PythonOperator(task_id="evaluate_and_log", python_callable=evaluate_and_log)
    t1 >> [t2, t3] >> t4
