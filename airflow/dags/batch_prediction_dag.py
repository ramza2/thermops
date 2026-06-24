"""DAG-008: 배치 예측 파이프라인 템플릿."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, log_pipeline_run


def load_champion_model(**context):
    log_pipeline_run("PREDICTION", "batch_prediction_dag", "RUNNING", "Champion 모델 로드")


def build_future_features(**context):
    log_pipeline_run("PREDICTION", "batch_prediction_dag", "RUNNING", "예측 Feature 생성")


def run_prediction(**context):
    log_pipeline_run("PREDICTION", "batch_prediction_dag", "RUNNING", "배치 예측 실행")


def save_results(**context):
    log_pipeline_run("PREDICTION", "batch_prediction_dag", "SUCCESS", "예측 결과 저장")


with DAG(
    dag_id="batch_prediction_dag",
    default_args=DEFAULT_ARGS,
    description="D+1/D+7 열수요 배치 예측",
    schedule="0 5 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "prediction"],
) as dag:
    t1 = PythonOperator(task_id="load_champion_model", python_callable=load_champion_model)
    t2 = PythonOperator(task_id="build_future_features", python_callable=build_future_features)
    t3 = PythonOperator(task_id="run_prediction", python_callable=run_prediction)
    t4 = PythonOperator(task_id="save_results", python_callable=save_results)
    [t1, t2] >> t3 >> t4
