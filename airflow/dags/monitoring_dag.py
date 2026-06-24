"""DAG-010: 모니터링 파이프라인 템플릿."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, log_pipeline_run


def match_actuals(**context):
    log_pipeline_run("MONITORING", "monitoring_dag", "RUNNING", "실제값 매칭")


def calculate_metrics(**context):
    log_pipeline_run("MONITORING", "monitoring_dag", "RUNNING", "성능 지표 계산")


def run_drift_check(**context):
    log_pipeline_run("MONITORING", "monitoring_dag", "RUNNING", "드리프트 점검")


def create_report(**context):
    log_pipeline_run("MONITORING", "monitoring_dag", "SUCCESS", "모니터링 리포트 생성")


with DAG(
    dag_id="monitoring_dag",
    default_args=DEFAULT_ARGS,
    description="성능 평가, 드리프트, 재학습 후보 판단",
    schedule="0 8 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "monitoring"],
) as dag:
    t1 = PythonOperator(task_id="match_actuals", python_callable=match_actuals)
    t2 = PythonOperator(task_id="calculate_metrics", python_callable=calculate_metrics)
    t3 = PythonOperator(task_id="run_drift_check", python_callable=run_drift_check)
    t4 = PythonOperator(task_id="create_report", python_callable=create_report)
    t1 >> t2 >> t3 >> t4
