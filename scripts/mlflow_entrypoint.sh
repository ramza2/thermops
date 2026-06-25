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
exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri postgresql://thermops:thermops@postgres:5432/thermops \
  --default-artifact-root s3://mlflow/
