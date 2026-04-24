"""Celery 后台任务：知识文件异步索引和记忆提炼。

目的：提供异步执行的后台任务，避免长耗时操作阻塞主对话流程。
结果：支持知识文件索引和 LLM 驱动的记忆提炼在后台执行。
"""

from __future__ import annotations

import asyncio
import base64
import logging

from celery import Celery

from core.config import get_settings

from .memory import MemoryManager

settings = get_settings()
logger = logging.getLogger(__name__)

# Celery 应用实例：使用 Redis 作为 broker 和 backend
celery_app = Celery(
    "ai_love",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务默认超时 10 分钟
    task_soft_time_limit=600,
    task_time_limit=660,
    # 工作进程并发数
    worker_concurrency=4,
)


@celery_app.task(
    bind=True,
    name="ai_love.index_knowledge_file",
    max_retries=3,
    default_retry_delay=30,
)
def index_knowledge_file(
    self,
    file_data_b64: str,
    filename: str,
    category: str = "relationship_knowledge",
    source: str = "",
) -> dict[str, object]:
    """异步知识文件索引任务：解析 → 切分 → Embedding → 入库。

    目的：在后台异步执行知识文件的完整索引流程，避免大文件索引阻塞 API 响应。
    结果：将文件内容解析、切分、嵌入后存入向量库，返回索引结果。
    """
    try:
        # 解码文件数据
        file_data = base64.b64decode(file_data_b64)
        logger.info(
            "开始异步索引知识文件: filename=%s, size=%d bytes, category=%s",
            filename,
            len(file_data),
            category,
        )

        # 延迟导入避免循环依赖
        from rag import RagService

        service = RagService()
        result = asyncio.run(
            service.index_file(
                file_data,
                filename,
                category=category,
                source=source or f"async:{filename}",
            )
        )
        logger.info("异步索引完成: filename=%s, chunks=%d", filename, result.chunks_written)
        return result.model_dump()

    except Exception as exc:
        logger.error("异步索引失败: filename=%s, error=%s", filename, exc)
        # 自动重试
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="ai_love.extract_and_save_memory",
    max_retries=2,
    default_retry_delay=10,
)
def extract_and_save_memory(
    self,
    user_id: str,
    user_message: str,
    assistant_reply: str,
    session_id: str | None = None,
) -> dict[str, object]:
    """LLM 驱动的记忆提炼任务：从对话中提取关键记忆并写入向量库。

    目的：使用 LLM 对对话内容进行智能提炼，提取值得长期记忆的关键信息。
    结果：将提炼后的记忆存入向量库，返回保存结果或跳过原因。
    """
    try:
        logger.info("开始 LLM 记忆提炼: user_id=%s", user_id)

        memory_manager = MemoryManager()

        async def _run_memory_pipeline() -> dict[str, object]:
            """在单个事件循环中顺序执行记忆提炼 + 分类 + 保存，避免重复创建事件循环。"""
            decision = await memory_manager.decide_memory(
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
            if not decision.should_store or not decision.memory_text:
                return {"status": "skipped", "reason": decision.reason_code}

            record_id = await memory_manager.save_memory(
                user_id,
                decision,
                session_id=session_id,
            )
            return {
                "status": "saved" if record_id else "skipped",
                "record_id": record_id,
                "memory": decision.memory_text,
                "canonical_key": decision.canonical_key,
                "memory_type": decision.memory_type,
                "importance_score": decision.importance_score,
                "confidence": decision.confidence,
                "merge_strategy": decision.merge_strategy,
            }

        result = asyncio.run(_run_memory_pipeline())
        logger.info("LLM 记忆提炼完成: user_id=%s, result=%s", user_id, result)
        return result

    except Exception as exc:
        logger.error("LLM 记忆提炼失败: user_id=%s, error=%s", user_id, exc)
        raise self.retry(exc=exc) from exc
