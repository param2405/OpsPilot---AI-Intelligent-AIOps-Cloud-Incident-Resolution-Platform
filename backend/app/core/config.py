from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and optional .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpsPilot AI"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "opspilot"
    postgres_password: str = "opspilot_dev_password"
    postgres_db: str = "opspilot"
    database_url: str | None = Field(default=None)

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_url: str | None = None

    mlflow_tracking_uri: str = "http://localhost:5000"

    aws_region: str = "us-east-1"
    s3_artifact_bucket: str | None = None
    s3_endpoint_url: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
