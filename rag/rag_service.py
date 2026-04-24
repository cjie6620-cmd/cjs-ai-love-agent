"""知识库管理服务：封装索引管道和混合检索器。"""

from __future__ import annotations

import logging
from pathlib import Path

from contracts.rag import (
    KnowledgeBatchIndexResponse,
    KnowledgeIndexResponse,
    KnowledgeIndexTextRequest,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResultItem,
)

from .data_loader import KnowledgeDataLoader
from .lexical_retriever import LexicalRetriever
from .pipeline import IngestionPipeline
from .retriever import KnowledgeRetriever
from .vector_store import PgVectorClient

logger = logging.getLogger(__name__)


class RagService:
    """知识库管理服务，提供文件索引、文本索引、检索三大能力。"""

    def __init__(self) -> None:
        self._vector_client = PgVectorClient()
        self._lexical_retriever = LexicalRetriever()
        self._pipeline = IngestionPipeline(
            vector_client=self._vector_client,
            lexical_retriever=self._lexical_retriever,
        )
        self._retriever = KnowledgeRetriever(
            vector_client=self._vector_client,
            lexical_retriever=self._lexical_retriever,
        )

    async def index_file(
        self,
        data: bytes,
        filename: str,
        category: str = "relationship_knowledge",
        source: str = "",
    ) -> KnowledgeIndexResponse:
        """索引单个文件。"""
        try:
            normalized_source = source or f"file:{filename}"
            doc_id = self._pipeline._build_doc_id(  # noqa: SLF001 - 服务层需要与 pipeline 保持同一 doc_id 规则
                title=filename,
                base_metadata={
                    "filename": filename,
                    "source": normalized_source,
                    "category": category,
                    "title": filename,
                },
            )
            deleted = await self._replace_existing_document(
                filename=filename,
                category=category,
                source=normalized_source,
                doc_id=doc_id,
            )
            written = await self._pipeline.ingest_file(
                data,
                filename,
                category=category,
                source=normalized_source,
            )
            logger.info(
                "文件索引完成: filename=%s, source=%s, deleted=%d, written=%d",
                filename,
                normalized_source,
                deleted,
                written,
            )
            return KnowledgeIndexResponse(
                success=True,
                filename=filename,
                chunks_written=written,
                message=f"成功索引 {written} 个 chunk",
            )
        except Exception as exc:
            logger.error("文件索引失败: filename=%s, error=%s", filename, exc)
            return KnowledgeIndexResponse(
                success=False,
                filename=filename,
                chunks_written=0,
                message=f"索引失败: {exc}",
            )

    async def index_text(self, request: KnowledgeIndexTextRequest) -> KnowledgeIndexResponse:
        """从纯文本直接索引入库。"""
        try:
            doc_id = self._pipeline._build_doc_id(  # noqa: SLF001
                title=request.title,
                base_metadata={
                    "title": request.title,
                    "source": request.source,
                    "category": request.category,
                },
            )
            await self._replace_existing_document(
                filename=request.title or "",
                category=request.category,
                source=request.source,
                doc_id=doc_id,
            )
            written = await self._pipeline.ingest_text(
                request.text,
                title=request.title,
                category=request.category,
                source=request.source,
            )
            return KnowledgeIndexResponse(
                success=True,
                filename="",
                chunks_written=written,
                message=f"成功索引 {written} 个 chunk",
            )
        except Exception as exc:
            logger.error("文本索引失败: title=%s, error=%s", request.title, exc)
            return KnowledgeIndexResponse(
                success=False,
                filename="",
                chunks_written=0,
                message=f"索引失败: {exc}",
            )

    async def index_knowledge_directory(
        self,
        directory: str | Path,
        category: str = "relationship_knowledge",
        source: str = "",
    ) -> KnowledgeBatchIndexResponse:
        """批量索引指定目录下所有支持的文件。"""
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return KnowledgeBatchIndexResponse(
                success=False,
                message=f"目录不存在: {directory}",
            )

        loader = KnowledgeDataLoader()
        files = loader.iter_supported_files(dir_path)
        if not files:
            return KnowledgeBatchIndexResponse(
                success=True,
                message=f"目录 {directory} 中无可索引文件",
            )

        results: list[KnowledgeIndexResponse] = []
        total_chunks = 0

        for file_path in files:
            data = file_path.read_bytes()
            result = await self.index_file(
                data,
                file_path.name,
                category=category,
                source=source or str(dir_path),
            )
            results.append(result)
            total_chunks += result.chunks_written
            logger.info(
                "索引进度: %s → %s (%d chunks)",
                file_path.name,
                "成功" if result.success else "失败",
                result.chunks_written,
            )

        success_count = sum(1 for result in results if result.success)
        return KnowledgeBatchIndexResponse(
            success=success_count > 0,
            total_files=len(files),
            total_chunks=total_chunks,
            results=results,
            message=f"共 {len(files)} 个文件，成功 {success_count} 个，写入 {total_chunks} 个 chunk",
        )

    async def search(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        """混合检索知识库。"""
        response = await self._retriever.search_with_context(
            [request.query],
            top_k=request.top_k,
            category=request.category,
        )
        items = [
            KnowledgeSearchResultItem(
                chunk_id=item.chunk_id,
                content=item.content,
                score=item.score,
                category=item.category,
                source=item.source,
                parent_id=item.parent_id,
                title=item.title,
                heading_path=item.heading_path,
                locator=item.locator,
                dense_score=item.dense_score,
                bm25_score=item.bm25_score,
                fusion_score=item.fusion_score,
                rerank_score=item.rerank_score,
            )
            for item in response.candidates
        ]
        return KnowledgeSearchResponse(
            query=request.query,
            results=items,
            total=len(items),
        )

    async def _delete_lexical_document(
        self,
        *,
        source: str,
        category: str,
        filename: str,
        doc_id: str,
    ) -> int:
        return await self._lexical_retriever.delete_document(
            source=source,
            category=category,
            filename=filename or None,
            doc_id=doc_id or None,
        )

    async def _replace_existing_document(
        self,
        *,
        filename: str,
        category: str,
        source: str,
        doc_id: str,
    ) -> int:
        """在重建单个文档索引前先清理旧数据。"""
        if not source:
            return 0
        deleted = self._vector_client.delete_knowledge(
            source=source,
            category=category,
            filename=filename or None,
            doc_id=doc_id or None,
        )
        try:
            await self._delete_lexical_document(
                source=source,
                category=category,
                filename=filename,
                doc_id=doc_id,
            )
        except Exception as exc:
            logger.warning("ES 预删除失败，继续后续重建: %s", exc)
        return deleted
