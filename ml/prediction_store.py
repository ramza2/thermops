"""예측 결과 저장."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine


def save_predictions(
    df: pd.DataFrame,
    prediction_job_id: str,
    model_version_id: str,
) -> int:
    engine = create_engine(os.getenv("THERMOps_DB_URL", "postgresql://thermops:thermops@localhost:5432/thermops"))
    records = []
    for _, row in df.iterrows():
        records.append({
            "prediction_job_id": prediction_job_id,
            "site_id": row["site_id"],
            "target_at": row["target_at"],
            "predicted_demand": row["predicted_demand"],
            "model_version_id": model_version_id,
            "created_at": datetime.utcnow(),
        })
    out = pd.DataFrame(records)
    out.to_sql("tb_heat_demand_prediction", engine, if_exists="append", index=False)
    return len(records)
