#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE thermops_airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'thermops_airflow')\gexec
EOSQL
