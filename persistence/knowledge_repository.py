"""知识库文档和异步任务仓储。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db_base import get_session_factory
from .models import KnowledgeDocument, KnowledgeJob


class KnowledgeRepository:
    """目的：封装知识文档、索引任务的 MySQL 读写。
    结果：提供 KnowledgeRepository 的结构化能力，供业务流程复用。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """目的：执行 __init__ 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        self.session_factory = session_factory or get_session_factory()

    def create_document_job(
        self,
        *,
        tenant_id: str,
        doc_id: str,
        title: str,
        filename: str,
        category: str,
        source: str,
        object_name: str,
        created_by: str,
        job_type: str,
        content_text: str = "",
    ) -> tuple[KnowledgeDocument, KnowledgeJob]:
        """目的：创建知识文档和对应的异步任务。
        结果：创建业务资源并返回创建结果。
        """
        with self.session_factory() as session:
            document = KnowledgeDocument(
                tenant_id=tenant_id,
                doc_id=doc_id,
                title=title,
                filename=filename,
                category=category,
                source=source,
                object_name=object_name,
                content_text=content_text,
                status="pending",
                created_by=created_by,
            )
            session.add(document)
            session.flush()
            job = KnowledgeJob(
                tenant_id=tenant_id,
                job_type=job_type,
                status="pending",
                document_id=document.id,
                filename=filename,
                progress=0,
                created_by=created_by,
            )
            session.add(job)
            session.flush()
            document.last_job_id = job.id
            session.commit()
            session.refresh(document)
            session.refresh(job)
            return document, job

    def create_reindex_all_job(self, *, tenant_id: str, created_by: str) -> KnowledgeJob:
        """目的：创建全量重建任务。
        结果：创建业务资源并返回创建结果。
        """
        with self.session_factory() as session:
            job = KnowledgeJob(
                tenant_id=tenant_id,
                job_type="reindex_all",
                status="pending",
                progress=0,
                created_by=created_by,
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def create_document_reindex_job(
        self,
        *,
        tenant_id: str,
        document_id: str,
        created_by: str,
    ) -> KnowledgeJob | None:
        """目的：创建单文档重建任务。
        结果：创建业务资源并返回创建结果。
        """
        with self.session_factory() as session:
            document = session.get(KnowledgeDocument, document_id)
            if document is None or document.tenant_id != tenant_id or document.status == "deleted":
                return None
            job = KnowledgeJob(
                tenant_id=tenant_id,
                job_type="reindex_document",
                status="pending",
                document_id=document.id,
                filename=document.filename,
                progress=0,
                created_by=created_by,
            )
            session.add(job)
            session.flush()
            document.last_job_id = job.id
            document.status = "pending"
            session.commit()
            session.refresh(job)
            return job

    def list_documents(self, tenant_id: str, *, status: str = "", keyword: str = "") -> list[KnowledgeDocument]:
        """目的：列出知识文档。
        结果：返回符合条件的数据列表。
        """
        normalized = keyword.strip().lower()
        with self.session_factory() as session:
            statement = (
                select(KnowledgeDocument)
                .where(KnowledgeDocument.tenant_id == tenant_id)
                .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.created_at.desc())
                .limit(200)
            )
            if status:
                statement = statement.where(KnowledgeDocument.status == status)
            documents = list(session.scalars(statement))
            if not normalized:
                return documents
            return [
                document
                for document in documents
                if normalized in document.title.lower() or normalized in document.filename.lower()
            ]

    def get_document(self, tenant_id: str, document_id: str) -> KnowledgeDocument | None:
        """目的：读取单个知识文档。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            document = session.get(KnowledgeDocument, document_id)
            if document is None or document.tenant_id != tenant_id:
                return None
            return document

    def get_document_by_id(self, document_id: str) -> KnowledgeDocument | None:
        """目的：Worker 内部按 ID 读取文档。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            return session.get(KnowledgeDocument, document_id)

    def list_jobs(self, tenant_id: str, *, status: str = "") -> list[KnowledgeJob]:
        """目的：列出知识任务。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            statement = (
                select(KnowledgeJob)
                .where(KnowledgeJob.tenant_id == tenant_id)
                .order_by(KnowledgeJob.created_at.desc())
                .limit(200)
            )
            if status:
                statement = statement.where(KnowledgeJob.status == status)
            return list(session.scalars(statement))

    def get_job(self, tenant_id: str, job_id: str) -> KnowledgeJob | None:
        """目的：读取单个知识任务。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            job = session.get(KnowledgeJob, job_id)
            if job is None or job.tenant_id != tenant_id:
                return None
            return job

    def get_job_by_id(self, job_id: str) -> KnowledgeJob | None:
        """目的：Worker 内部按 ID 读取任务。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            return session.get(KnowledgeJob, job_id)

    def mark_job_running(self, job_id: str) -> bool:
        """目的：标记任务运行中。
        结果：完成当前实例行为并返回约定结果。
        """
        now = datetime.now(UTC)
        with self.session_factory() as session:
            job = session.get(KnowledgeJob, job_id)
            if job is None:
                return False
            if job.status == "canceled":
                return False
            job.status = "running"
            job.started_at = job.started_at or now
            job.progress = max(job.progress, 5)
            if job.document_id:
                document = session.get(KnowledgeDocument, job.document_id)
                if document is not None:
                    document.status = "indexing"
            session.commit()
            return True

    def mark_job_succeeded(self, job_id: str, *, chunk_count: int = 0, result_json: dict[str, Any] | None = None) -> None:
        """目的：标记任务成功。
        结果：完成当前实例行为并返回约定结果。
        """
        now = datetime.now(UTC)
        with self.session_factory() as session:
            job = session.get(KnowledgeJob, job_id)
            if job is None:
                return
            if job.status == "canceled":
                return
            job.status = "succeeded"
            job.progress = 100
            job.finished_at = now
            job.result_json = result_json or {}
            job.error_message = ""
            if job.document_id:
                document = session.get(KnowledgeDocument, job.document_id)
                if document is not None:
                    document.status = "active"
                    document.chunk_count = chunk_count
                    document.error_message = ""
            session.commit()

    def mark_job_failed(self, job_id: str, *, error_message: str) -> None:
        """目的：标记任务失败。
        结果：完成当前实例行为并返回约定结果。
        """
        now = datetime.now(UTC)
        with self.session_factory() as session:
            job = session.get(KnowledgeJob, job_id)
            if job is None:
                return
            if job.status == "canceled":
                return
            job.status = "failed"
            job.finished_at = now
            job.error_message = error_message[:2000]
            if job.document_id:
                document = session.get(KnowledgeDocument, job.document_id)
                if document is not None:
                    document.status = "failed"
                    document.error_message = error_message[:2000]
            session.commit()

    def mark_job_canceled(self, tenant_id: str, job_id: str) -> bool:
        """目的：取消 pending/running 任务。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            job = session.get(KnowledgeJob, job_id)
            if job is None or job.tenant_id != tenant_id:
                return False
            if job.status not in {"pending", "running"}:
                return False
            job.status = "canceled"
            job.finished_at = datetime.now(UTC)
            session.commit()
            return True

    def reset_job_for_retry(self, tenant_id: str, job_id: str) -> KnowledgeJob | None:
        """目的：把失败或取消的任务重置为待执行，供后台手动重试。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            job = session.get(KnowledgeJob, job_id)
            if job is None or job.tenant_id != tenant_id:
                return None
            if job.status not in {"failed", "canceled"}:
                return None
            job.status = "pending"
            job.progress = 0
            job.error_message = ""
            job.started_at = None
            job.finished_at = None
            if job.document_id:
                document = session.get(KnowledgeDocument, job.document_id)
                if document is not None and document.status != "deleted":
                    document.status = "pending"
                    document.error_message = ""
            session.commit()
            session.refresh(job)
            return job

    def soft_delete_document(self, tenant_id: str, document_id: str) -> KnowledgeDocument | None:
        """目的：软删除知识文档。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            document = session.get(KnowledgeDocument, document_id)
            if document is None or document.tenant_id != tenant_id:
                return None
            document.status = "deleted"
            session.commit()
            session.refresh(document)
            return document

    def list_active_documents(self, tenant_id: str) -> list[KnowledgeDocument]:
        """目的：Worker 全量重建时列出 active 文档。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            return list(
                session.scalars(
                    select(KnowledgeDocument)
                    .where(KnowledgeDocument.tenant_id == tenant_id)
                    .where(KnowledgeDocument.status == "active")
                    .order_by(KnowledgeDocument.updated_at.desc())
                )
            )
