"""Celery 后台任务：知识文件异步索引和记忆提炼。

目的：提供异步执行的后台任务，避免长耗时操作阻塞主对话流程。
结果：支持知识文件索引和 LLM 驱动的记忆提炼在后台执行。
"""

from __future__ import annotations

import asyncio
import logging

from celery import Celery

from core.config import get_settings
from llm import LlmClient
from contracts.rag import KnowledgeIndexTextRequest
from persistence import ConversationRepository, KnowledgeRepository
from rag.storage import MinioClient
from security import RedisService

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


def _run_file_index_job(job_id: str) -> dict[str, object]:
    """目的：执行 _run_file_index_job 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    repository = KnowledgeRepository()
    if not repository.mark_job_running(job_id):
        return {"status": "canceled"}
    job = repository.get_job_by_id(job_id)
    if job is None or not job.document_id:
        raise ValueError("知识索引任务不存在")
    document = repository.get_document_by_id(job.document_id)
    if document is None:
        raise ValueError("知识文档不存在")

    if not document.object_name:
        if not document.content_text:
            raise RuntimeError("文本知识缺少原文内容，无法重建")
        return _run_text_index_for_document(repository, job_id, document.content_text)

    file_data = MinioClient(log_startup=False).download_file(document.object_name)
    if file_data is None:
        raise RuntimeError("知识文件无法从对象存储读取")
    logger.info(
        "开始异步索引知识文件: filename=%s, size=%d bytes, category=%s",
        document.filename,
        len(file_data),
        document.category,
    )

    from rag import RagService

    result = asyncio.run(
        RagService().index_file(
            file_data,
            document.filename,
            category=document.category,
            source=document.source,
            tenant_id=document.tenant_id,
            created_by=document.created_by,
            document_id=document.id,
        )
    )
    if not result.success:
        raise RuntimeError(result.message)
    repository.mark_job_succeeded(
        job_id,
        chunk_count=result.chunks_written,
        result_json=result.model_dump(),
    )
    logger.info("异步索引完成: filename=%s, chunks=%d", document.filename, result.chunks_written)
    return result.model_dump()


def _run_text_index_for_document(
    repository: KnowledgeRepository,
    job_id: str,
    text: str,
) -> dict[str, object]:
    """目的：执行 _run_text_index_for_document 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    job = repository.get_job_by_id(job_id)
    if job is None or not job.document_id:
        raise ValueError("知识索引任务不存在")
    document = repository.get_document_by_id(job.document_id)
    if document is None:
        raise ValueError("知识文档不存在")
    request = KnowledgeIndexTextRequest(
        title=document.title,
        text=text,
        category=document.category,
        source=document.source,
    )
    from rag import RagService

    result = asyncio.run(
        RagService().index_text(
            request,
            tenant_id=document.tenant_id,
            created_by=document.created_by,
            document_id=document.id,
        )
    )
    if not result.success:
        raise RuntimeError(result.message)
    repository.mark_job_succeeded(
        job_id,
        chunk_count=result.chunks_written,
        result_json=result.model_dump(),
    )
    return result.model_dump()


@celery_app.task(
    bind=True,
    name="ai_love.index_knowledge_file",
    max_retries=3,
    default_retry_delay=30,
)
def index_knowledge_file(
    self,
    job_id: str,
) -> dict[str, object]:
    """目的：在后台异步执行知识文件的完整索引流程，避免大文件索引阻塞 API 响应。
    结果：将文件内容解析、切分、嵌入后存入向量库，返回索引结果。
    """
    repository = KnowledgeRepository()
    try:
        return _run_file_index_job(job_id)

    except Exception as exc:
        repository.mark_job_failed(job_id, error_message=str(exc))
        logger.error("异步索引失败: job=%s, error=%s", job_id, exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="ai_love.index_knowledge_text",
    max_retries=3,
    default_retry_delay=30,
)
def index_knowledge_text(self, job_id: str, payload: dict[str, object]) -> dict[str, object]:
    """目的：异步文本知识索引任务。
    结果：完成当前业务处理并返回约定结果。
    """
    repository = KnowledgeRepository()
    try:
        if not repository.mark_job_running(job_id):
            return {"status": "canceled"}
        job = repository.get_job_by_id(job_id)
        if job is None:
            raise ValueError("知识索引任务不存在")
        request = KnowledgeIndexTextRequest.model_validate(payload)
        document = repository.get_document_by_id(job.document_id) if job.document_id else None
        if document is not None and document.content_text:
            request = KnowledgeIndexTextRequest(
                title=document.title,
                text=document.content_text,
                category=document.category,
                source=document.source,
            )
        from rag import RagService

        result = asyncio.run(
            RagService().index_text(
                request,
                tenant_id=job.tenant_id,
                created_by=job.created_by,
                document_id=job.document_id or "",
            )
        )
        if not result.success:
            raise RuntimeError(result.message)
        repository.mark_job_succeeded(
            job_id,
            chunk_count=result.chunks_written,
            result_json=result.model_dump(),
        )
        return result.model_dump()
    except Exception as exc:
        repository.mark_job_failed(job_id, error_message=str(exc))
        logger.error("文本知识索引失败: job=%s, error=%s", job_id, exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="ai_love.reindex_knowledge_document",
    max_retries=3,
    default_retry_delay=30,
)
def reindex_knowledge_document(self, job_id: str) -> dict[str, object]:
    """目的：异步重建单个知识文档。
    结果：完成当前业务处理并返回约定结果。
    """
    repository = KnowledgeRepository()
    try:
        return _run_file_index_job(job_id)
    except Exception as exc:
        repository.mark_job_failed(job_id, error_message=str(exc))
        logger.error("单文档知识重建失败: job=%s, error=%s", job_id, exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="ai_love.reindex_knowledge_all",
    max_retries=1,
    default_retry_delay=60,
)
def reindex_knowledge_all(self, job_id: str) -> dict[str, object]:
    """目的：异步重建当前租户全部 active 知识文档。
    结果：完成当前业务处理并返回约定结果。
    """
    repository = KnowledgeRepository()
    lock_key = ""
    try:
        if not repository.mark_job_running(job_id):
            return {"status": "canceled"}
        job = repository.get_job_by_id(job_id)
        if job is None:
            raise ValueError("知识重建任务不存在")
        lock_key = f"knowledge:reindex:{job.tenant_id}"
        documents = repository.list_active_documents(job.tenant_id)
        total_chunks = 0
        from rag import RagService

        service = RagService()
        for document in documents:
            if document.object_name:
                file_data = MinioClient(log_startup=False).download_file(document.object_name)
                if file_data is None:
                    logger.warning("跳过无法读取的知识文件: document=%s", document.id)
                    continue
                result = asyncio.run(
                    service.index_file(
                        file_data,
                        document.filename,
                        category=document.category,
                        source=document.source,
                        tenant_id=document.tenant_id,
                        created_by=document.created_by,
                        document_id=document.id,
                    )
                )
            elif document.content_text:
                result = asyncio.run(
                    service.index_text(
                        KnowledgeIndexTextRequest(
                            title=document.title,
                            text=document.content_text,
                            category=document.category,
                            source=document.source,
                        ),
                        tenant_id=document.tenant_id,
                        created_by=document.created_by,
                        document_id=document.id,
                    )
                )
            else:
                logger.warning("跳过缺少原始内容的知识文档: document=%s", document.id)
                continue
            if not result.success:
                raise RuntimeError(result.message)
            total_chunks += result.chunks_written
        repository.mark_job_succeeded(
            job_id,
            chunk_count=total_chunks,
            result_json={"documents": len(documents), "chunks": total_chunks},
        )
        return {"documents": len(documents), "chunks": total_chunks}
    except Exception as exc:
        repository.mark_job_failed(job_id, error_message=str(exc))
        logger.error("全量知识重建失败: job=%s, error=%s", job_id, exc)
        raise self.retry(exc=exc) from exc
    finally:
        if lock_key:
            RedisService(log_startup=False).delete(lock_key)


@celery_app.task(
    bind=True,
    name="ai_love.refresh_session_summary",
    max_retries=3,
    default_retry_delay=30,
)
def refresh_session_summary(self, session_id: str) -> dict[str, object]:
    """目的：异步刷新会话滚动摘要。
    结果：刷新登录凭证并返回新的登录态信息。
    """
    try:
        settings = get_settings()
        repository = ConversationRepository()
        checkpoint = repository.get_summary_checkpoint(session_id)
        messages = repository.list_messages_after(
            session_id,
            str(checkpoint.get("last_message_id", "")),
            limit=settings.conversation_cache_max_messages,
        )
        if not messages:
            return {"status": "skipped", "reason": "no_pending_messages"}

        old_summary = str(checkpoint.get("summary_text", "") or "")
        transcript_lines: list[str] = []
        for item in messages:
            content = item.content.strip()
            if not content:
                continue
            role = "用户" if item.role == "user" else "助手"
            if item.role == "assistant" and item.reply_status == "interrupted":
                content = f"上一轮 assistant 回复被用户手动终止，以下是已生成的部分内容：\n{content}"
            transcript_lines.append(f"{role}：{content}")
        transcript = "\n".join(transcript_lines)
        system_prompt = "你是会话上下文摘要器，只输出稳定、克制、可继续对话使用的中文摘要。"
        user_prompt = (
            "请基于旧摘要和新增对话，生成新的会话滚动摘要。\n"
            "保留：关系背景、用户当前状态、关键事实、已给出的重要建议、未解决问题。\n"
            "忽略：寒暄、重复情绪词、无长期上下文价值的闲聊。\n"
            f"最多 {settings.conversation_summary_max_chars} 字。\n\n"
            f"旧摘要：\n{old_summary or '无'}\n\n"
            f"新增对话：\n{transcript}"
        )
        summary_text = LlmClient.for_memory_analysis().generate_sync(
            system_prompt,
            user_prompt,
        ).strip()
        if not summary_text:
            summary_text = old_summary
        summary_text = summary_text[:settings.conversation_summary_max_chars]

        covered_count_raw = checkpoint.get("covered_message_count", 0)
        covered_count = int(covered_count_raw) if isinstance(covered_count_raw, int | str) else 0
        covered_count += len(messages)
        last_message_id = messages[-1].id
        repository.update_session_summary(
            session_id,
            summary_text=summary_text,
            covered_message_count=covered_count,
            last_message_id=last_message_id,
        )
        logger.info(
            "会话滚动摘要刷新完成: session=%s, covered=%d, last_message_id=%s",
            session_id,
            covered_count,
            last_message_id,
        )
        return {
            "status": "updated",
            "covered_message_count": covered_count,
            "last_message_id": last_message_id,
        }
    except Exception as exc:
        logger.error("会话滚动摘要刷新失败: session=%s, error=%s", session_id, exc)
        raise self.retry(exc=exc) from exc
