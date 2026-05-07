from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_SERVICE_ROOT = Path(__file__).resolve().parents[2]  # workflow-service/


class Settings(BaseSettings):
    # Defaults keep local dev (Postman) unblocked; override via env or `.env`.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/workflow_db"
    CORE_SERVICE_URL: str = "http://localhost:8001"
    ENTITY_SERVICE_URL: str = "http://localhost:8002"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8003"
    ENTITY_SERVICE_TOKEN: str = "dev-token"
    JWT_PUBLIC_KEY: str = "dev-public-key-placeholder"
    APP_NAME: str = "workflow-service"
    # APP_ENV: str = "dev"

    model_config = SettingsConfigDict(env_file=str(_SERVICE_ROOT / ".env"), extra="ignore")


settings = Settings()
