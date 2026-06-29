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
MLFLOW_BACKEND_STORE_URI="$(python3 -c "
from urllib.parse import quote_plus
import os
u = quote_plus(os.environ.get('POSTGRES_USER', 'thermops'))
p = quote_plus(os.environ.get('POSTGRES_PASSWORD', 'thermops'))
db = os.environ.get('POSTGRES_DB', 'thermops')
print(f'postgresql://{u}:{p}@postgres:5432/{db}')
")"
exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
  --default-artifact-root s3://mlflow/
