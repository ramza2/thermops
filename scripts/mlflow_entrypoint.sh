#!/bin/bash
set -e
pip install --quiet psycopg2-binary boto3
exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri postgresql://thermops:thermops@postgres:5432/thermops \
  --default-artifact-root s3://mlflow/
