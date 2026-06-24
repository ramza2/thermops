"""DAG-005: Feature 생성 파이프라인 템플릿."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, log_pipeline_run


def load_clean_data(**context):
    log_pipeline_run("FEATURE", "feature_build_dag", "RUNNING", "정제 데이터 로드")


def build_features(**context):
    log_pipeline_run("FEATURE", "feature_build_dag", "RUNNING", "lag/rolling Feature 생성")


def save_feature_set(**context):
    log_pipeline_run("FEATURE", "feature_build_dag", "SUCCESS", "Feature Set 저장")


with DAG(
    dag_id="feature_build_dag",
    default_args=DEFAULT_ARGS,
    description="학습/예측 공통 Feature 생성",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "feature"],
) as dag:
    t1 = PythonOperator(task_id="load_clean_data", python_callable=load_clean_data)
    t2 = PythonOperator(task_id="build_features", python_callable=build_features)
    t3 = PythonOperator(task_id="save_feature_set", python_callable=save_feature_set)
    t1 >> t2 >> t3
