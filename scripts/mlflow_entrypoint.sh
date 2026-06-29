#!/bin/bash
set -e
pip install --quiet psycopg2-binary boto3
python - <<'PY'
import os
import boto3
from botocore.exceptions import ClientError

endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
)
try:
    s3.head_bucket(Bucket="mlflow")
except ClientError:
    s3.create_bucket(Bucket="mlflow")
    print("Created MinIO bucket: mlflow")
PY
PG_USER="${POSTGRES_USER:-thermops}"
PG_PASS="${POSTGRES_PASSWORD:-thermops}"
PG_DB="${POSTGRES_DB:-thermops}"
exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri "postgresql://${PG_USER}:${PG_PASS}@postgres:5432/${PG_DB}" \
  --default-artifact-root s3://mlflow/
