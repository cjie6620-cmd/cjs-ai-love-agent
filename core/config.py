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
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 model_config 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 model_config 值。
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用名称，用于接口文档、日志和服务标识展示
    # 目的：保存 app_name 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 app_name 值。
    app_name: str = "AI Love Agent API"
    # 当前运行环境标识，例如 local / dev / test / prod
    # 目的：保存 app_env 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 app_env 值。
    app_env: str = "local"
    # 是否开启调试模式，开启后日志更详细
    # 目的：保存 debug 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 debug 值。
    debug: bool = True
    # 允许跨域访问的前端来源列表，多个地址用英文逗号分隔
    # 目的：保存 cors_origins 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 cors_origins 值。
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:8081,http://127.0.0.1:8081"
    )
    # 允许跨域的来源正则，适合匹配本地多个端口
    # 目的：保存 cors_origin_regex 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 cors_origin_regex 值。
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # MySQL 连接串，主业务库使用这个地址
    # 目的：保存 mysql_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mysql_url 值。
    mysql_url: str = "mysql+pymysql://ai_love:ai_love@127.0.0.1:3306/ai_love"
    # Redis 连接串，用于限流、短期记忆和缓存
    # 目的：保存 redis_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 redis_url 值。
    redis_url: str = "redis://127.0.0.1:6379/0"
    # pgvector / PostgreSQL 连接串，用于长期记忆和知识向量检索
    # 目的：保存 vector_db_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 vector_db_url 值。
    vector_db_url: str = "postgresql+psycopg://ai_love:change-me@127.0.0.1:5432/ai_love_vector"
    # 向量维度，必须与当前 embedding 模型输出维度保持一致
    # 目的：保存 vector_dimension 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 vector_dimension 值。
    vector_dimension: int = 1536
    # Elasticsearch 地址列表，支持逗号分隔多个节点
    # 目的：保存 es_hosts 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 es_hosts 值。
    es_hosts: str = "http://127.0.0.1:9200"
    # Elasticsearch 中知识分片使用的索引名
    # 目的：保存 es_index 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 es_index 值。
    es_index: str = "knowledge_chunks"
    # Elasticsearch 用户名
    # 目的：保存 es_username 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 es_username 值。
    es_username: str = "elastic"
    # Elasticsearch 密码
    # 目的：保存 es_password 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 es_password 值。
    es_password: str = "change-me"
    # Elasticsearch 请求超时时间，单位毫秒
    # 目的：保存 es_timeout_ms 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 es_timeout_ms 值。
    es_timeout_ms: int = 3000

    # MinIO 服务地址，格式通常是 host:port
    # 目的：保存 minio_endpoint 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 minio_endpoint 值。
    minio_endpoint: str = "127.0.0.1:9000"
    # MinIO 访问账号
    # 目的：保存 minio_access_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 minio_access_key 值。
    minio_access_key: str = "minioadmin"
    # MinIO 访问密钥
    # 目的：保存 minio_secret_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 minio_secret_key 值。
    minio_secret_key: str = "change-me"
    # MinIO 中业务文件使用的桶名称
    # 目的：保存 minio_bucket 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 minio_bucket 值。
    minio_bucket: str = "ai-love"
    # 默认租户 ID，企业版 RBAC 和知识库隔离都会以租户为边界
    # 目的：保存 default_tenant_id 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 default_tenant_id 值。
    default_tenant_id: str = "default"
    # 逗号分隔的管理员登录名；命中后登录/注册时自动授予 admin 角色
    # 目的：保存 admin_login_names 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 admin_login_names 值。
    admin_login_names: str = ""
    # 知识库文件上传大小上限，单位 MB
    # 目的：保存 knowledge_max_upload_mb 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_max_upload_mb 值。
    knowledge_max_upload_mb: int = 10

    # 主聊天模型提供方标识
    # 目的：保存 llm_provider 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 llm_provider 值。
    llm_provider: str = "xai_router"
    # 主模型服务的兼容 OpenAI Base URL
    # 目的：保存 llm_base_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 llm_base_url 值。
    llm_base_url: str = "https://api.xairouter.com/v1"
    # 默认聊天模型名称
    # 目的：保存 llm_model 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 llm_model 值。
    llm_model: str = "gpt-5"
    # token 统计后端，支持 auto / tiktoken / huggingface / char_estimate
    # 目的：保存 tokenizer_backend 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tokenizer_backend 值。
    tokenizer_backend: str = "auto"
    # HuggingFace tokenizer 仓库名，仅在对应后端启用时使用
    # 目的：保存 hf_tokenizer_repo 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 hf_tokenizer_repo 值。
    hf_tokenizer_repo: str = ""
    # xAI Router API Key
    # 目的：保存 xai_api_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 xai_api_key 值。
    xai_api_key: str = ""

    # 是否启用 LangSmith 集成
    # 目的：保存 langsmith_enabled 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_enabled 值。
    langsmith_enabled: bool = False
    # 是否开启 LangSmith 链路追踪
    # 目的：保存 langsmith_tracing 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_tracing 值。
    langsmith_tracing: bool = False
    # LangSmith API Key
    # 目的：保存 langsmith_api_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_api_key 值。
    langsmith_api_key: str = ""
    # LangSmith 项目名
    # 目的：保存 langsmith_project 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_project 值。
    langsmith_project: str = ""
    # LangSmith 服务地址
    # 目的：保存 langsmith_endpoint 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_endpoint 值。
    langsmith_endpoint: str = ""
    # LangSmith 工作区 ID，可选
    # 目的：保存 langsmith_workspace_id 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_workspace_id 值。
    langsmith_workspace_id: str = ""
    # LangSmith 采样率，范围 0 到 1
    # 目的：保存 langsmith_sample_rate 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_sample_rate 值。
    langsmith_sample_rate: float = 1.0
    # LangSmith 隐私模式，true 时尽量隐藏敏感输入输出
    # 目的：保存 langsmith_privacy_mode 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_privacy_mode 值。
    langsmith_privacy_mode: bool = True
    # 聊天回复 Prompt 的 LangSmith 标识，可选
    # 目的：保存 langsmith_prompt_chat_reply 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_prompt_chat_reply 值。
    langsmith_prompt_chat_reply: str = ""
    # 记忆决策 Prompt 的 LangSmith 标识，可选
    # 目的：保存 langsmith_prompt_memory_decision 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langsmith_prompt_memory_decision 值。
    langsmith_prompt_memory_decision: str = ""

    # Tavily API Key，用于联网搜索
    # 目的：保存 tavily_api_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tavily_api_key 值。
    tavily_api_key: str = ""
    # 高德地图 API Key
    # 目的：保存 amap_maps_api_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 amap_maps_api_key 值。
    amap_maps_api_key: str = ""
    # MCP 传输协议类型，当前默认使用 streamable_http
    # 目的：保存 mcp_transport 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_transport 值。
    mcp_transport: str = "streamable_http"
    # 高德 MCP 服务地址
    # 目的：保存 amap_mcp_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 amap_mcp_url 值。
    amap_mcp_url: str = "http://127.0.0.1:3100/mcp"
    # 高德 MCP 额外请求头，JSON 字符串格式
    # 目的：保存 amap_mcp_headers_json 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 amap_mcp_headers_json 值。
    amap_mcp_headers_json: str = ""

    # LangGraph Checkpointer 使用的 PostgreSQL 地址，留空时回退到 vector_db_url
    # 目的：保存 langgraph_checkpoint_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 langgraph_checkpoint_url 值。
    langgraph_checkpoint_url: str = ""

    # DeepSeek API Key，作为备用模型时使用
    # 目的：保存 deepseek_api_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 deepseek_api_key 值。
    deepseek_api_key: str = ""
    # DeepSeek 服务地址
    # 目的：保存 deepseek_base_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 deepseek_base_url 值。
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    # DeepSeek 默认模型名
    # 目的：保存 deepseek_model 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 deepseek_model 值。
    deepseek_model: str = "deepseek-chat"

    # RocketMQ NameServer 地址
    # 目的：保存 rocketmq_namesrv_addr 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_namesrv_addr 值。
    rocketmq_namesrv_addr: str = "127.0.0.1:9876"
    # RocketMQ 生产者组名
    # 目的：保存 rocketmq_producer_group 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_producer_group 值。
    rocketmq_producer_group: str = "ai_love_memory_producer"
    # 长期记忆抽取消息主题名
    # 目的：保存 rocketmq_memory_topic 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_memory_topic 值。
    rocketmq_memory_topic: str = "ai_love_memory_extraction"
    # 长期记忆抽取消息标签
    # 目的：保存 rocketmq_memory_tag 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_memory_tag 值。
    rocketmq_memory_tag: str = "memory.extract.v1"
    # 长期记忆消费者组名
    # 目的：保存 rocketmq_memory_consumer_group 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_memory_consumer_group 值。
    rocketmq_memory_consumer_group: str = "ai_love_memory_consumer"
    # RocketMQ 发送超时时间，单位毫秒
    # 目的：保存 rocketmq_send_timeout_ms 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_send_timeout_ms 值。
    rocketmq_send_timeout_ms: int = 3000
    # RocketMQ 最大重试消费次数
    # 目的：保存 rocketmq_max_reconsume_times 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rocketmq_max_reconsume_times 值。
    rocketmq_max_reconsume_times: int = 16
    # 启动时是否探测 Celery worker 健康状态
    # 目的：保存 celery_worker_probe_enabled 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 celery_worker_probe_enabled 值。
    celery_worker_probe_enabled: bool = True

    # MCP 工具调用是否需要审批
    # 目的：保存 mcp_require_approval 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_require_approval 值。
    mcp_require_approval: bool = False
    # 是否启用 Tavily MCP 能力
    # 目的：保存 mcp_tavily_enabled 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_tavily_enabled 值。
    mcp_tavily_enabled: bool = True
    # 是否启用高德地图 MCP 能力
    # 目的：保存 mcp_amap_enabled 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_amap_enabled 值。
    mcp_amap_enabled: bool = False

    # Embedding 模型名称，用于文本向量化
    # 目的：保存 embedding_model 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 embedding_model 值。
    embedding_model: str = "text-embedding-3-small"
    # Embedding 批处理大小
    # 目的：保存 embedding_batch_size 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 embedding_batch_size 值。
    embedding_batch_size: int = 32
    # Rerank 服务地址
    # 目的：保存 rerank_service_url 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_service_url 值。
    rerank_service_url: str = "http://127.0.0.1:8001"
    # Rerank 服务鉴权 Key，可选
    # 目的：保存 rerank_api_key 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_api_key 值。
    rerank_api_key: str = ""
    # Rerank 服务超时时间，单位毫秒
    # 目的：保存 rerank_timeout_ms 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_timeout_ms 值。
    rerank_timeout_ms: int = 5000
    # 重排模型名称
    # 目的：保存 rerank_model_name 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_model_name 值。
    rerank_model_name: str = "BAAI/bge-reranker-v2-m3"
    # 向量召回候选数量
    # 目的：保存 hybrid_dense_top_k 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 hybrid_dense_top_k 值。
    hybrid_dense_top_k: int = 20
    # BM25 词法召回候选数量
    # 目的：保存 hybrid_bm25_top_k 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 hybrid_bm25_top_k 值。
    hybrid_bm25_top_k: int = 20
    # 双路融合后保留的候选数量
    # 目的：保存 hybrid_fusion_top_k 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 hybrid_fusion_top_k 值。
    hybrid_fusion_top_k: int = 12
    # 最终放入 Prompt 的父级上下文数量
    # 目的：保存 prompt_parent_top_k 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 prompt_parent_top_k 值。
    prompt_parent_top_k: int = 4
    # 目的：保存 rerank_top_n 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_top_n 值。
    rerank_top_n: int = 5
    # 是否启用自定义接口 API Key 鉴权，true 时请求必须携带约定鉴权头
    # 目的：保存 api_key_enabled 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 api_key_enabled 值。
    api_key_enabled: bool = False
    # 自定义接口 API Key 的具体值，仅在启用 API Key 鉴权时生效
    # 目的：保存 api_key_value 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 api_key_value 值。
    api_key_value: str = ""
    # JWT access token 的签名密钥，用于登录态签发与校验
    # 目的：保存 auth_jwt_secret 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 auth_jwt_secret 值。
    auth_jwt_secret: str = "change-me-dev-auth-secret"
    # access token 有效期，单位分钟
    # 目的：保存 auth_access_token_minutes 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 auth_access_token_minutes 值。
    auth_access_token_minutes: int = 30
    # refresh token 有效期，单位天
    # 目的：保存 auth_refresh_token_days 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 auth_refresh_token_days 值。
    auth_refresh_token_days: int = 30
    # 未登录访客每天可发送的对话次数上限，超限后要求登录
    # 目的：保存 guest_daily_message_limit 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 guest_daily_message_limit 值。
    guest_daily_message_limit: int = 1
    # 访客 Cookie 是否自动按环境开启 Secure；local/dev 关闭，其他环境开启
    # 目的：保存 guest_cookie_secure_auto 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 guest_cookie_secure_auto 值。
    guest_cookie_secure_auto: bool = True
    # 匿名访客 IP 维度兜底限流每日上限，防止清 Cookie 绕过试用额度
    # 目的：保存 guest_ip_daily_message_limit 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 guest_ip_daily_message_limit 值。
    guest_ip_daily_message_limit: int = 30
    # 会话热缓存最多保留的最近消息数，只用于加速上下文构造
    # 目的：保存 conversation_cache_max_messages 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_cache_max_messages 值。
    conversation_cache_max_messages: int = 40
    # 会话热缓存 TTL，单位秒
    # 目的：保存 conversation_cache_ttl_seconds 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_cache_ttl_seconds 值。
    conversation_cache_ttl_seconds: int = 7200
    # 本轮放入 Prompt 的最近原文消息 token 预算
    # 目的：保存 conversation_context_token_budget 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_context_token_budget 值。
    conversation_context_token_budget: int = 1800
    # 未摘要消息达到该数量后触发异步滚动摘要
    # 目的：保存 conversation_summary_trigger_messages 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_summary_trigger_messages 值。
    conversation_summary_trigger_messages: int = 12
    # 未摘要消息估算 token 达到该值后触发异步滚动摘要
    # 目的：保存 conversation_summary_trigger_tokens 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_summary_trigger_tokens 值。
    conversation_summary_trigger_tokens: int = 2500
    # 会话滚动摘要最大字符数
    # 目的：保存 conversation_summary_max_chars 字段，用于 Settings 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_summary_max_chars 值。
    conversation_summary_max_chars: int = 1200
    # 是否启用聊天回答分级缓存
    # 目的：保存 response_cache_enabled 字段，用于控制 L1/L2 回答缓存开关。
    # 结果：生产环境可以通过配置快速启停缓存能力。
    response_cache_enabled: bool = True
    # L1 精确回答缓存 TTL，单位秒
    # 目的：保存 response_cache_exact_ttl_seconds 字段，用于控制 Redis 精确缓存生命周期。
    # 结果：重复提交和短时间重试可以快速命中。
    response_cache_exact_ttl_seconds: int = 600
    # L2 语义回答缓存 TTL，单位秒
    # 目的：保存 response_cache_semantic_ttl_seconds 字段，用于控制 pgvector 语义缓存生命周期。
    # 结果：相似问题在短窗口内可以复用高置信回复。
    response_cache_semantic_ttl_seconds: int = 1800
    # L2 语义缓存命中阈值
    # 目的：保存 response_cache_semantic_threshold 字段，用于控制语义复用的相似度门槛。
    # 结果：避免低相关问题误用缓存回答。
    response_cache_semantic_threshold: float = 0.94
    # 回答缓存版本
    # 目的：保存 response_cache_version 字段，用于在 Prompt 或响应结构变化时主动隔离旧缓存。
    # 结果：修改版本后旧缓存自然失效。
    response_cache_version: str = "chat_response_cache.v1"

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: bool | str) -> bool:
        """目的：标准化 debug 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return cls._normalize_bool(value)

    @field_validator(
        "langsmith_enabled",
        "langsmith_tracing",
        "langsmith_privacy_mode",
        "mcp_require_approval",
        "mcp_tavily_enabled",
        "mcp_amap_enabled",
        "api_key_enabled",
        "guest_cookie_secure_auto",
        "response_cache_enabled",
        mode="before",
    )
    @classmethod
    def normalize_bool_flags(cls, value: bool | str) -> bool:
        """目的：标准化 bool_flags 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return cls._normalize_bool(value)

    @field_validator("tokenizer_backend", mode="before")
    @classmethod
    def normalize_tokenizer_backend(cls, value: str) -> str:
        """目的：标准化 tokenizer_backend 字段输入，统一边界值和格式。
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
        """目的：清洗环境变量中的传输类型，避免大小写或空值影响 MCP 初始化。
        结果：返回可直接用于路由判断的传输类型，默认使用 streamable_http。
        """
        normalized = str(value).strip().lower()
        return normalized or "streamable_http"

    @field_validator("hf_tokenizer_repo", mode="before")
    @classmethod
    def normalize_hf_tokenizer_repo(cls, value: str) -> str:
        """目的：标准化 hf_tokenizer_repo 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return str(value).strip()

    @field_validator("langsmith_sample_rate", mode="before")
    @classmethod
    def normalize_langsmith_sample_rate(cls, value: float | str) -> float:
        """目的：标准化 langsmith_sample_rate 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return 1.0
        return min(max(rate, 0.0), 1.0)

    @staticmethod
    def _normalize_bool(value: bool | str) -> bool:
        """目的：执行当前步骤对应的处理逻辑。
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
        """目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def amap_mcp_headers(self) -> dict[str, str]:
        """目的：解析环境变量中的 JSON 请求头配置，并过滤非法键值。
        结果：返回可传给 MCP HTTP transport 的字符串字典。
        """
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
        """目的：把逗号分隔的 Elasticsearch 地址配置拆成可遍历列表。
        结果：返回去空格后的 host 列表，空项会被过滤。
        """
        return [host.strip() for host in self.es_hosts.split(",") if host.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def admin_login_name_set(self) -> set[str]:
        """目的：返回配置中的管理员登录名集合。
        结果：完成当前实例行为并返回约定结果。
        """
        return {
            item.strip().lower()
            for item in self.admin_login_names.split(",")
            if item.strip()
        }

    @computed_field  # type: ignore[misc]
    @property
    def guest_cookie_secure(self) -> bool:
        """目的：根据环境决定匿名访客 Cookie 是否启用 Secure。
        结果：完成当前实例行为并返回约定结果。
        """
        if not self.guest_cookie_secure_auto:
            return False
        return self.app_env.strip().lower() not in {"local", "dev", "development", "test"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """目的：获取返回全局缓存的配置实例。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    return Settings()
