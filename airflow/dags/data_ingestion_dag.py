"""DAG-002/003: 데이터 적재 파이프라인 템플릿."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, log_pipeline_run


def extract_heat_actual(**context):
    log_pipeline_run("INGESTION", "data_ingestion_dag", "RUNNING", "열수요 실적 추출")
    return {"rows": 24}


def extract_weather(**context):
    log_pipeline_run("INGESTION", "data_ingestion_dag", "RUNNING", "기상 데이터 추출")
    return {"rows": 24}


def upsert_data(**context):
    log_pipeline_run("INGESTION", "data_ingestion_dag", "SUCCESS", "적재 완료")


with DAG(
    dag_id="data_ingestion_dag",
    default_args=DEFAULT_ARGS,
    description="열수요/기상 데이터 적재",
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thermops", "ingestion"],
) as dag:
    t1 = PythonOperator(task_id="extract_heat_actual", python_callable=extract_heat_actual)
    t2 = PythonOperator(task_id="extract_weather", python_callable=extract_weather)
    t3 = PythonOperator(task_id="upsert_data", python_callable=upsert_data)
    [t1, t2] >> t3
