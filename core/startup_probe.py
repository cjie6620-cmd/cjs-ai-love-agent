"""应用启动阶段的基础设施探活。"""

from __future__ import annotations

import logging
import re
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
    """单个基础设施启动检查结果。"""

    name: str
    ok: bool
    endpoint: str
    detail: str

    @property
    def status(self) -> str:
        return "ok" if self.ok else "fail"

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "endpoint": self.endpoint,
            "detail": self.detail,
        }


def _mask_url(url: str) -> str:
    """脱敏 URL 中的密码，避免日志泄露敏感信息。"""
    return re.sub(r"(://[^@]*:)[^@]*(@)", r"\1***\2", url)


def _build_result(name: str, ok: bool, endpoint: str, detail: str) -> StartupProbeResult:
    return StartupProbeResult(name=name, ok=ok, endpoint=endpoint, detail=detail)


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    return f"{exc.__class__.__name__}: {message}" if message else exc.__class__.__name__


def probe_mysql(settings: Settings | None = None) -> StartupProbeResult:
    """检查 MySQL 连通性。"""
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
    """检查 Redis 连通性。"""
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
    """检查 Celery worker 是否在线，避免记忆任务只入队不执行。"""
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
    """检查 RocketMQ NameServer 配置与客户端依赖。"""
    resolved_settings = settings or get_settings()
    endpoint = resolved_settings.rocketmq_namesrv_addr
    try:
        from rocketmq.client import Producer

        producer = Producer(f"{resolved_settings.rocketmq_producer_group}_probe")
        producer.set_name_server_address(endpoint)
        return _build_result(
            "RocketMQ",
            True,
            endpoint,
            f"客户端可用，topic={resolved_settings.rocketmq_memory_topic}",
        )
    except Exception as exc:
        return _build_result("RocketMQ", False, endpoint, _format_exception(exc))


def probe_vector_db(settings: Settings | None = None) -> StartupProbeResult:
    """检查 pgvector 数据库连通性与扩展可用性。"""
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
    """检查高德 MCP 是否可握手并成功返回工具列表。"""
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
    """检查 MinIO 连通性，并确保 bucket 存在。"""
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
    """检查 Elasticsearch 连通性。"""
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
    """检查独立重排服务连通性。"""
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
    level = logger.info if result.ok else logger.warning
    level(
        "[启动检查] %s | %s | endpoint=%s | detail=%s",
        result.name,
        "SUCCESS" if result.ok else "FAILED",
        result.endpoint,
        result.detail,
    )


async def run_startup_probes(settings: Settings | None = None) -> list[StartupProbeResult]:
    """执行所有基础设施启动检查，并输出汇总日志。"""
    resolved_settings = settings or get_settings()
    results = [
        probe_mysql(resolved_settings),
        probe_redis(resolved_settings),
        probe_celery_worker(resolved_settings),
        probe_rocketmq(resolved_settings),
        probe_vector_db(resolved_settings),
        await probe_elasticsearch(resolved_settings),
        await probe_reranker(resolved_settings),
        probe_minio(resolved_settings),
    ]
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
