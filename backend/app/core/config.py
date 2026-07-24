from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DATABASE_URL 직접 지정 시 우선. 미지정 시 POSTGRES_* 로 조합(URL 인코딩 적용).
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    postgres_host: str = Field(default="postgres", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_user: str = Field(default="thermops", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="thermops", validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="thermops", validation_alias="POSTGRES_DB")
    mlflow_tracking_uri: str = "http://localhost:5000"
    cors_origins: str = "http://localhost:5173"
    api_prefix: str = "/api/v1"
    thermops_project_root: str | None = None
    airflow_base_url: str = "http://airflow:8080"
    airflow_username: str = "admin"
    airflow_password: str = "admin"
    # R10-S10 Run Due Worker
    run_due_worker_enabled: bool = Field(default=False, validation_alias="THERMOOPS_RUN_DUE_WORKER_ENABLED")
    run_due_worker_name: str = Field(default="run-due-worker-1", validation_alias="THERMOOPS_RUN_DUE_WORKER_NAME")
    run_due_worker_mode: str = Field(default="loop", validation_alias="THERMOOPS_RUN_DUE_WORKER_MODE")
    run_due_poll_interval_seconds: int = Field(default=60, validation_alias="THERMOOPS_RUN_DUE_POLL_INTERVAL_SECONDS")
    run_due_lock_ttl_seconds: int = Field(default=120, validation_alias="THERMOOPS_RUN_DUE_LOCK_TTL_SECONDS")
    run_due_max_batch_size: int = Field(default=20, validation_alias="THERMOOPS_RUN_DUE_MAX_BATCH_SIZE")
    run_due_fail_fast: bool = Field(default=False, validation_alias="THERMOOPS_RUN_DUE_FAIL_FAST")
    run_due_notification_enabled: bool = Field(default=True, validation_alias="THERMOOPS_RUN_DUE_NOTIFICATION_ENABLED")
    run_due_graceful_timeout_seconds: int = Field(default=30, validation_alias="THERMOOPS_RUN_DUE_GRACEFUL_TIMEOUT_SECONDS")
    run_due_log_level: str = Field(default="INFO", validation_alias="THERMOOPS_RUN_DUE_LOG_LEVEL")
    # R11-S7-6 Visual Pipeline Run Worker (Option C)
    vp_run_executor: str = Field(default="background_tasks", validation_alias="THERMOOPS_VP_RUN_EXECUTOR")
    vp_run_worker_enabled: bool = Field(default=False, validation_alias="THERMOOPS_VP_RUN_WORKER_ENABLED")
    vp_run_worker_id: str = Field(default="", validation_alias="THERMOOPS_VP_RUN_WORKER_ID")
    vp_run_worker_mode: str = Field(default="loop", validation_alias="THERMOOPS_VP_RUN_WORKER_MODE")
    vp_run_worker_poll_interval_seconds: int = Field(
        default=5, validation_alias="THERMOOPS_VP_RUN_WORKER_POLL_INTERVAL_SECONDS"
    )
    vp_run_worker_lock_ttl_seconds: int = Field(
        default=120, validation_alias="THERMOOPS_VP_RUN_WORKER_LOCK_TTL_SECONDS"
    )
    vp_run_worker_max_batch_size: int = Field(
        default=1, validation_alias="THERMOOPS_VP_RUN_WORKER_MAX_BATCH_SIZE"
    )
    vp_run_worker_log_level: str = Field(default="INFO", validation_alias="THERMOOPS_VP_RUN_WORKER_LOG_LEVEL")
    # R11-S7-8 Visual Pipeline Schedule Activation
    vp_schedule_activation_enabled: bool = Field(
        default=False, validation_alias="THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"
    )
    vp_schedule_worker_enabled: bool = Field(
        default=False, validation_alias="THERMOOPS_VP_SCHEDULE_WORKER_ENABLED"
    )
    vp_schedule_worker_mode: str = Field(default="loop", validation_alias="THERMOOPS_VP_SCHEDULE_WORKER_MODE")
    vp_schedule_worker_poll_interval_seconds: int = Field(
        default=30, validation_alias="THERMOOPS_VP_SCHEDULE_WORKER_POLL_INTERVAL_SECONDS"
    )
    vp_schedule_worker_max_batch_size: int = Field(
        default=10, validation_alias="THERMOOPS_VP_SCHEDULE_WORKER_MAX_BATCH_SIZE"
    )
    vp_schedule_worker_id: str = Field(default="", validation_alias="THERMOOPS_VP_SCHEDULE_WORKER_ID")
    vp_schedule_min_interval_seconds: int = Field(
        default=300, validation_alias="THERMOOPS_VP_SCHEDULE_MIN_INTERVAL_SECONDS"
    )
    vp_schedule_worker_log_level: str = Field(
        default="INFO", validation_alias="THERMOOPS_VP_SCHEDULE_WORKER_LOG_LEVEL"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def project_root(self) -> Path:
        if self.thermops_project_root:
            return Path(self.thermops_project_root)
        # backend/app/core/config.py -> repo root
        return Path(__file__).resolve().parents[3]


@lru_cache
def get_settings() -> Settings:
    return Settings()
