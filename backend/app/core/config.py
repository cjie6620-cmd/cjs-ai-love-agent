from functools import lru_cache

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一管理后端配置，避免把地址和密钥散落在业务代码中。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Love Agent API"
    app_env: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    mysql_url: str = "mysql+pymysql://ai_love:ai_love@127.0.0.1:3306/ai_love"
    redis_url: str = "redis://127.0.0.1:6379/0"
    vector_db_url: str = "postgresql+psycopg://ai_love:ai_love@127.0.0.1:5432/ai_love_vector"
    db_auto_create_tables: bool = False
    vector_auto_create_tables: bool = False
    vector_dimension: int = 1536

    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "ai-love"

    llm_provider: str = "xai_router"
    llm_base_url: str = "https://api.xairouter.com/v1"
    llm_model: str = "gpt-5"
    xai_api_key: str = ""
    langsmith_tracing: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return False

    @computed_field  # type: ignore[misc]
    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
