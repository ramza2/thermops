from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1 import (
    common,
    dashboard,
    data,
    feature,
    mapping,
    model,
    monitoring,
    pipeline,
    prediction,
    training,
)

settings = get_settings()

app = FastAPI(
    title="THERMOps API",
    description="열수요 예측 모델 운영 자동화 플랫폼 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings.api_prefix

app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(common.router, prefix=api_prefix)
app.include_router(data.router, prefix=api_prefix)
app.include_router(mapping.router, prefix=api_prefix)
app.include_router(feature.router, prefix=api_prefix)
app.include_router(training.router, prefix=api_prefix)
app.include_router(model.router, prefix=api_prefix)
app.include_router(prediction.router, prefix=api_prefix)
app.include_router(monitoring.router, prefix=api_prefix)
app.include_router(pipeline.router, prefix=api_prefix)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "thermops-backend"}
