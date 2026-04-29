"""应用启动阶段的基础设施探活。

目的：在应用启动时检查数据库、缓存、消息队列、向量库和外部服务是否可用。
结果：输出统一的探活结果，方便本地排障和部署环境健康观测。
"""

from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass

import httpx
from redis import ConnectionError as RedisConnectionError
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import Settings, get_settings
from mcp.transport import McpStreamableHttpTransport
from persistence.db_base import get_engine
from rag.vector_store.base import get_vector_engine

logger = logging.getLogger(__name__)

_VECTOR_REQUIRED_TABLES = (
    "memory_embeddings",
    "knowledge_embeddings",
    "style_sample_embeddings",
)


@dataclass(slots=True)
class StartupProbeResult:
    """目的：承载某个依赖的探活名称、状态、端点和诊断详情。
    结果：日志、健康接口和测试可以复用同一份结果结构。
    """

    # 目的：保存 name 字段，用于 StartupProbeResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str
    # 目的：保存 ok 字段，用于 StartupProbeResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 ok 值。
    ok: bool
    # 目的：保存 endpoint 字段，用于 StartupProbeResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 endpoint 值。
    endpoint: str
    # 目的：保存 detail 字段，用于 StartupProbeResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 detail 值。
    detail: str

    @property
    def status(self) -> str:
        """目的：把布尔状态转换成接口和日志更易读的状态字符串。
        结果：成功返回 ok，失败返回 fail。
        """
        return "ok" if self.ok else "fail"

    def to_dict(self) -> dict[str, str]:
        """目的：把 dataclass 结果序列化为 API 可直接返回的结构。
        结果：返回包含 name、status、endpoint、detail 的字典。
        """
        return {
            "name": self.name,
            "status": self.status,
            "endpoint": self.endpoint,
            "detail": self.detail,
        }


def _mask_url(url: str) -> str:
    """目的：避免启动日志泄露数据库、Redis 等连接串里的敏感信息。
    结果：返回密码被替换为星号的 URL。
    """
    return re.sub(r"(://[^@]*:)[^@]*(@)", r"\1***\2", url)


def _build_result(name: str, ok: bool, endpoint: str, detail: str) -> StartupProbeResult:
    """目的：减少各探针重复组装 StartupProbeResult 的代码。
    结果：返回字段完整的 StartupProbeResult。
    """
    return StartupProbeResult(name=name, ok=ok, endpoint=endpoint, detail=detail)


def _format_exception(exc: Exception) -> str:
    """目的：把异常类型和消息压缩成适合日志展示的诊断文本。
    结果：返回非空的异常说明字符串。
    """
    message = str(exc).strip()
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__


def probe_mysql(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证主业务数据库是否可以建立连接并执行轻量 SQL。
    结果：返回 MySQL 探活成功或失败的统一结果。
    """
    resolved_settings = settings or get_settings()
    endpoint = _mask_url(resolved_settings.mysql_url)
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return _build_result("MySQL", True, endpoint, "连接成功")
    except SQLAlchemyError as exc:
        return _build_result("MySQL", False, endpoint, _format_exception(exc))
    except Exception as exc:  # pragma: no cover
        return _build_result("MySQL", False, endpoint, _format_exception(exc))


def probe_redis(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证缓存和限流依赖是否可以连接并响应 PING。
    结果：返回 Redis 探活成功或失败的统一结果。
    """
    resolved_settings = settings or get_settings()
    endpoint = _mask_url(resolved_settings.redis_url)
    try:
        client = Redis.from_url(
            resolved_settings.redis_url,
            decode_responses=False,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        client.ping()
        return _build_result("Redis", True, endpoint, "PING 成功")
    except (RedisConnectionError, Exception) as exc:
        return _build_result("Redis", False, endpoint, _format_exception(exc))


def probe_celery_worker(settings: Settings | None = None) -> StartupProbeResult:
    """目的：确认后台任务 worker 已连接，避免记忆任务只入队不执行。
    结果：返回 worker 在线列表或失败原因。
    """
    resolved_settings = settings or get_settings()
    endpoint = _mask_url(resolved_settings.redis_url)
    try:
        from agents.worker import celery_app

        responses = celery_app.control.inspect(timeout=3).ping() or {}
        if not responses:
            return _build_result("CeleryWorker", False, endpoint, "未检测到在线 worker")
        worker_names = ",".join(sorted(responses.keys()))
        return _build_result("CeleryWorker", True, endpoint, f"worker 在线: {worker_names}")
    except Exception as exc:
        return _build_result("CeleryWorker", False, endpoint, _format_exception(exc))


def probe_rocketmq(settings: Settings | None = None) -> StartupProbeResult:
    """目的：用 TCP 连接探测替代 Windows 下不可用的 RocketMQ SDK 初始化。
    结果：返回 NameServer 是否可达和长期记忆 topic 诊断信息。
    """
    resolved_settings = settings or get_settings()
    endpoint = resolved_settings.rocketmq_namesrv_addr
    try:
        host, port_text = endpoint.rsplit(":", 1)
        with socket.create_connection((host, int(port_text)), timeout=3):
            pass
        return _build_result(
            "RocketMQ",
            True,
            endpoint,
            f"NameServer TCP 连接成功，topic={resolved_settings.rocketmq_memory_topic}",
        )
    except Exception as exc:
        return _build_result("RocketMQ", False, endpoint, _format_exception(exc))


def probe_vector_db(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证向量数据库、vector 扩展和关键业务向量表是否就绪。
    结果：返回 VectorDB 探活结果和缺失表详情。
    """
    resolved_settings = settings or get_settings()
    endpoint = _mask_url(resolved_settings.vector_db_url)
    try:
        engine = get_vector_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            has_vector_ext = bool(
                conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                ).scalar()
            )
            existing_tables = {
                str(row[0])
                for row in conn.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        """
                    )
                ).all()
            }
        if not has_vector_ext:
            return _build_result("VectorDB", False, endpoint, "数据库可连接，但未安装 vector 扩展")
        missing_tables = [name for name in _VECTOR_REQUIRED_TABLES if name not in existing_tables]
        if missing_tables:
            return _build_result(
                "VectorDB",
                False,
                endpoint,
                f"数据库可连接，但缺少业务向量表: {', '.join(missing_tables)}",
            )
        return _build_result("VectorDB", True, endpoint, "连接成功，vector 扩展可用")
    except SQLAlchemyError as exc:
        return _build_result("VectorDB", False, endpoint, _format_exception(exc))
    except Exception as exc:  # pragma: no cover
        return _build_result("VectorDB", False, endpoint, _format_exception(exc))


async def probe_amap_mcp(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证 MCP transport、鉴权头和远端工具列表是否可用。
    结果：返回 AmapMCP 探活结果和工具数量或失败原因。
    """
    resolved_settings = settings or get_settings()
    endpoint = resolved_settings.amap_mcp_url.rstrip("/") if resolved_settings.amap_mcp_url else "-"
    if resolved_settings.mcp_transport != "streamable_http":
        return _build_result(
            "AmapMCP",
            False,
            endpoint,
            f"当前仅支持 streamable_http，实际为 {resolved_settings.mcp_transport or '-'}",
        )
    if not resolved_settings.amap_mcp_url:
        return _build_result("AmapMCP", False, endpoint, "未配置 AMAP_MCP_URL")

    transport = McpStreamableHttpTransport(
        mcp_url=resolved_settings.amap_mcp_url,
        api_key=resolved_settings.amap_maps_api_key or None,
        extra_headers=resolved_settings.amap_mcp_headers,
    )
    try:
        tools = await transport.list_tools()
        if not tools:
            return _build_result("AmapMCP", False, endpoint, "连接成功，但工具列表为空")
        return _build_result("AmapMCP", True, endpoint, f"连接成功，tools={len(tools)}")
    except Exception as exc:
        return _build_result("AmapMCP", False, endpoint, _format_exception(exc))
    finally:
        try:
            await transport.close()
        except Exception:  # pragma: no cover
            pass


def probe_minio(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证对象存储可达，并在 bucket 缺失时完成最小初始化。
    结果：返回 MinIO 探活结果和 bucket 可用状态。
    """
    resolved_settings = settings or get_settings()
    endpoint = resolved_settings.minio_endpoint
    bucket = resolved_settings.minio_bucket
    try:
        from minio import Minio
        import urllib3

        client = Minio(
            endpoint=endpoint,
            access_key=resolved_settings.minio_access_key,
            secret_key=resolved_settings.minio_secret_key,
            secure=False,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=1.0, read=2.0),
                retries=urllib3.Retry(total=0, connect=0, read=0, redirect=0),
            ),
        )
        bucket_exists = client.bucket_exists(bucket)
        if not bucket_exists:
            client.make_bucket(bucket)
            return _build_result("MinIO", True, endpoint, f"连接成功，已创建 bucket={bucket}")
        return _build_result("MinIO", True, endpoint, f"连接成功，bucket={bucket} 可用")
    except Exception as exc:
        return _build_result("MinIO", False, endpoint, _format_exception(exc))


async def probe_elasticsearch(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证 BM25 召回依赖的 Elasticsearch 集群健康接口是否可用。
    结果：返回 Elasticsearch 探活结果、集群状态和集群名称。
    """
    resolved_settings = settings or get_settings()
    endpoint = (
        resolved_settings.es_host_list[0]
        if resolved_settings.es_host_list
        else "http://127.0.0.1:9200"
    )
    auth: tuple[str, str] | None = None
    if resolved_settings.es_username:
        auth = (resolved_settings.es_username, resolved_settings.es_password)

    try:
        async with httpx.AsyncClient(
            base_url=endpoint.rstrip("/"),
            auth=auth,
            timeout=resolved_settings.es_timeout_ms / 1000,
        ) as client:
            response = await client.get("/_cluster/health")
            response.raise_for_status()
            payload = response.json()
        cluster_status = str(payload.get("status", "unknown"))
        cluster_name = str(payload.get("cluster_name", "")).strip()
        detail = f"连接成功，cluster_status={cluster_status}"
        if cluster_name:
            detail = f"{detail}，cluster={cluster_name}"
        return _build_result("Elasticsearch", True, endpoint, detail)
    except Exception as exc:
        return _build_result("Elasticsearch", False, endpoint, _format_exception(exc))


async def probe_reranker(settings: Settings | None = None) -> StartupProbeResult:
    """目的：验证混合检索精排依赖的 reranker-api 健康接口是否可用。
    结果：返回 Reranker 探活结果和健康状态。
    """
    resolved_settings = settings or get_settings()
    endpoint = resolved_settings.rerank_service_url.rstrip("/")
    headers: dict[str, str] = {}
    if resolved_settings.rerank_api_key:
        headers["Authorization"] = "Bearer ***"

    try:
        async with httpx.AsyncClient(
            base_url=endpoint,
            timeout=resolved_settings.rerank_timeout_ms / 1000,
        ) as client:
            response = await client.get("/health", headers=headers)
            response.raise_for_status()
            payload = response.json()
        return _build_result(
            "Reranker",
            True,
            endpoint,
            f"连接成功，health={payload.get('status', 'unknown')}",
        )
    except Exception as exc:
        return _build_result("Reranker", False, endpoint, _format_exception(exc))


def _log_probe_result(result: StartupProbeResult) -> None:
    """目的：按成功或失败选择日志级别，并保持启动检查日志格式一致。
    结果：输出一条包含依赖名、状态、端点和详情的日志。
    """
    level = logger.info if result.ok else logger.warning
    level(
        "[启动检查] %s | %s | endpoint=%s | detail=%s",
        result.name,
        "SUCCESS" if result.ok else "FAILED",
        result.endpoint,
        result.detail,
    )


async def run_startup_probes(settings: Settings | None = None) -> list[StartupProbeResult]:
    """目的：按配置串行运行核心依赖探针，并补充可选 Celery/MCP 探针。
    结果：返回所有探活结果，同时输出成功数和失败项汇总。
    """
    resolved_settings = settings or get_settings()
    results = [
        probe_mysql(resolved_settings),
        probe_redis(resolved_settings),
        probe_rocketmq(resolved_settings),
        probe_vector_db(resolved_settings),
        await probe_elasticsearch(resolved_settings),
        await probe_reranker(resolved_settings),
        probe_minio(resolved_settings),
    ]
    if resolved_settings.celery_worker_probe_enabled:
        results.append(probe_celery_worker(resolved_settings))
    if resolved_settings.mcp_amap_enabled:
        results.append(await probe_amap_mcp(resolved_settings))

    for result in results:
        _log_probe_result(result)

    success_count = sum(1 for item in results if item.ok)
    failed_items = [item.name for item in results if not item.ok]
    summary = (
        f"[启动检查] 基础设施检查完成: total={len(results)}, success={success_count}, "
        f"failed={len(failed_items)}, failed_items={','.join(failed_items) or '-'}"
    )
    if failed_items:
        logger.warning(summary)
    else:
        logger.info(summary)
    return results
