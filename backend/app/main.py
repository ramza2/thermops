from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1 import (
    api_connector,
    common,
    dashboard,
    data,
    dataset_version,
    external_code_mapping,
    feature,
    feature_column_role,
    feature_recipe,
    mapping,
    model,
    monitoring,
    pipeline,
    pipeline_builder,
    prediction,
    prediction_entity,
    sample_external,
    standard_dataset,
    system,
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
app.include_router(api_connector.router, prefix=api_prefix)
app.include_router(prediction_entity.router, prefix=api_prefix)
app.include_router(external_code_mapping.router, prefix=api_prefix)
app.include_router(data.router, prefix=api_prefix)
app.include_router(sample_external.router, prefix=api_prefix)
app.include_router(mapping.router, prefix=api_prefix)
app.include_router(standard_dataset.router, prefix=api_prefix)
app.include_router(feature.router, prefix=api_prefix)
app.include_router(feature_column_role.router, prefix=api_prefix)
app.include_router(feature_recipe.router, prefix=api_prefix)
app.include_router(dataset_version.router, prefix=api_prefix)
app.include_router(training.router, prefix=api_prefix)
app.include_router(model.router, prefix=api_prefix)
app.include_router(prediction.router, prefix=api_prefix)
app.include_router(monitoring.router, prefix=api_prefix)
app.include_router(pipeline.router, prefix=api_prefix)
app.include_router(pipeline_builder.router, prefix=api_prefix)
app.include_router(system.router, prefix=api_prefix)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "thermops-backend"}
