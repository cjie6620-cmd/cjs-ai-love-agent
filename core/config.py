"""应用配置统一出口。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """统一管理应用配置，避免业务模块互相借道取配置。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Love Agent API"
    app_env: str = "local"
    debug: bool = True
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    )
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    mysql_url: str = "mysql+pymysql://ai_love:ai_love@127.0.0.1:3306/ai_love"
    redis_url: str = "redis://127.0.0.1:6379/0"
    vector_db_url: str = "postgresql+psycopg://ai_love:change-me@127.0.0.1:5432/ai_love_vector"
    vector_dimension: int = 1536
    es_hosts: str = "http://127.0.0.1:9200"
    es_index: str = "knowledge_chunks"
    es_username: str = "elastic"
    es_password: str = "change-me"
    es_timeout_ms: int = 3000

    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "change-me"
    minio_bucket: str = "ai-love"

    llm_provider: str = "xai_router"
    llm_base_url: str = "https://api.xairouter.com/v1"
    llm_model: str = "gpt-5"
    tokenizer_backend: str = "auto"
    hf_tokenizer_repo: str = ""
    xai_api_key: str = ""

    langsmith_enabled: bool = False
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = ""
    langsmith_endpoint: str = ""
    langsmith_workspace_id: str = ""
    langsmith_sample_rate: float = 1.0
    langsmith_privacy_mode: bool = True
    langsmith_prompt_chat_reply: str = ""
    langsmith_prompt_memory_decision: str = ""

    tavily_api_key: str = ""
    amap_maps_api_key: str = ""
    mcp_transport: str = "streamable_http"
    amap_mcp_url: str = "http://127.0.0.1:3100/mcp"
    amap_mcp_headers_json: str = ""

    langgraph_checkpoint_url: str = ""
    langgraph_use_checkpointer: bool = True

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    mcp_require_approval: bool = False
    mcp_tavily_enabled: bool = True
    mcp_amap_enabled: bool = False

    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 32
    rerank_service_url: str = "http://127.0.0.1:8001"
    rerank_api_key: str = ""
    rerank_timeout_ms: int = 5000
    rerank_model_name: str = "BAAI/bge-reranker-v2-m3"
    hybrid_dense_top_k: int = 20
    hybrid_bm25_top_k: int = 20
    hybrid_fusion_top_k: int = 12
    prompt_parent_top_k: int = 4
    rerank_top_n: int = 5
    api_key_enabled: bool = False
    api_key_value: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: bool | str) -> bool:
        """标准化 debug 字段输入。
        
        目的：标准化 debug 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return cls._normalize_bool(value)

    @field_validator(
        "langsmith_enabled",
        "langsmith_tracing",
        "langsmith_privacy_mode",
        "langgraph_use_checkpointer",
        "mcp_require_approval",
        "mcp_tavily_enabled",
        "mcp_amap_enabled",
        "api_key_enabled",
        mode="before",
    )
    @classmethod
    def normalize_bool_flags(cls, value: bool | str) -> bool:
        """标准化 bool_flags 字段输入。
        
        目的：标准化 bool_flags 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return cls._normalize_bool(value)

    @field_validator("tokenizer_backend", mode="before")
    @classmethod
    def normalize_tokenizer_backend(cls, value: str) -> str:
        """标准化 tokenizer_backend 字段输入。
        
        目的：标准化 tokenizer_backend 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        normalized = str(value).strip().lower()
        allowed = {"auto", "tiktoken", "huggingface", "char_estimate"}
        if normalized in allowed:
            return normalized
        return "auto"

    @field_validator("mcp_transport", mode="before")
    @classmethod
    def normalize_mcp_transport(cls, value: str) -> str:
        """标准化 MCP 传输配置。"""
        normalized = str(value).strip().lower()
        return normalized or "streamable_http"

    @field_validator("hf_tokenizer_repo", mode="before")
    @classmethod
    def normalize_hf_tokenizer_repo(cls, value: str) -> str:
        """标准化 hf_tokenizer_repo 字段输入。
        
        目的：标准化 hf_tokenizer_repo 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return str(value).strip()

    @field_validator("langsmith_sample_rate", mode="before")
    @classmethod
    def normalize_langsmith_sample_rate(cls, value: float | str) -> float:
        """标准化 langsmith_sample_rate 字段输入。
        
        目的：标准化 langsmith_sample_rate 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return 1.0
        return min(max(rate, 0.0), 1.0)

    @staticmethod
    def _normalize_bool(value: bool | str) -> bool:
        """_normalize_bool 方法。
        
        目的：执行当前步骤对应的处理逻辑。
        结果：返回当前步骤的处理结果，供后续流程继续使用。
        """
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production", ""}:
            return False
        return False

    @computed_field  # type: ignore[misc]
    @property
    def allowed_origins(self) -> list[str]:
        """执行 allowed_origins 方法。

        目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def amap_mcp_headers(self) -> dict[str, str]:
        """返回高德 MCP 的额外请求头。"""
        raw = self.amap_mcp_headers_json.strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in payload.items()
            if key and value is not None
        }

    @computed_field  # type: ignore[misc]
    @property
    def es_host_list(self) -> list[str]:
        """返回 ES 地址列表。"""
        return [host.strip() for host in self.es_hosts.split(",") if host.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回全局缓存的配置实例。
    
    目的：获取返回全局缓存的配置实例。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    return Settings()
