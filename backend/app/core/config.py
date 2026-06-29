from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://thermops:thermops@localhost:5432/thermops"
    mlflow_tracking_uri: str = "http://localhost:5000"
    cors_origins: str = "http://localhost:5173"
    api_prefix: str = "/api/v1"
    thermops_project_root: str | None = None
    airflow_base_url: str = "http://airflow:8080"
    airflow_username: str = "admin"
    airflow_password: str = "admin"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def project_root(self) -> Path:
        if self.thermops_project_root:
            return Path(self.thermops_project_root)
        # backend/app/core/config.py -> repo root
        return Path(__file__).resolve().parents[3]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
