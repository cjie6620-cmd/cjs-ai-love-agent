"""离线索引管道：解析 -> 清洗 -> parent-child 切片 -> pgvector/ES 写入。

目的：把原始知识文件转换成可向量检索和关键词检索的索引数据。
结果：知识内容同时写入 pgvector 和 Elasticsearch，供 RAG 混合检索使用。
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from .chunking import ParentChildChunkStrategy
from .chunking.base import ChunkStrategy, TextChunk
from .cleaner import TextCleaner
from .embeddings import EmbeddingService
from .ingestion import ParserRegistry
from .lexical_retriever import LexicalRetriever
from .vector_store import PgVectorClient

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """目的：编排解析、清洗、切片、embedding、向量写入和 ES 写入。
    结果：上层服务可以通过文件或纯文本入口完成知识建库。
    """

    def __init__(
        self,
        parser_registry: ParserRegistry | None = None,
        chunk_strategy: ChunkStrategy | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_client: PgVectorClient | None = None,
        lexical_retriever: LexicalRetriever | None = None,
        cleaner: TextCleaner | None = None,
    ) -> None:
        """目的：装配解析器、切片策略、embedding、向量库、关键词召回器和清洗器。
        结果：实例具备从原始文本到混合索引写入的完整能力。
        """
        self.parser_registry = parser_registry or ParserRegistry()
        self.chunk_strategy = chunk_strategy or ParentChildChunkStrategy(child_size=480, child_overlap=80)
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_client = vector_client or PgVectorClient()
        self.lexical_retriever = lexical_retriever or LexicalRetriever()
        self.cleaner = cleaner or TextCleaner()

    async def ingest_file(
        self,
        data: bytes,
        filename: str,
        *,
        category: str = "relationship_knowledge",
        source: str = "",
        tenant_id: str = "default",
        created_by: str = "",
        document_id: str = "",
    ) -> int:
        """目的：解析上传文件并统一清洗后进入切片和索引写入流程。
        结果：返回写入的 chunk 数量。
        """
        doc = self.parser_registry.parse(data, filename=filename)
        cleaned_text = self.cleaner.clean(doc.text, doc.metadata)
        logger.info("文档解析完成: filename=%s, text_len=%d", filename, len(cleaned_text))

        base_metadata = {
            "filename": filename,
            "source": source,
            "category": category,
            "tenant_id": tenant_id,
            "created_by": created_by,
            **doc.metadata,
            "document_id": document_id,
        }
        return await self._chunk_embed_store(
            text=cleaned_text,
            title=filename,
            category=category,
            source=source,
            tenant_id=tenant_id,
            created_by=created_by,
            base_metadata=base_metadata,
        )

    async def ingest_text(
        self,
        text: str,
        *,
        title: str = "",
        category: str = "relationship_knowledge",
        source: str = "",
        tenant_id: str = "default",
        created_by: str = "",
        document_id: str = "",
    ) -> int:
        """目的：跳过文件解析，把已有文本按同一规则清洗、切片并入库。
        结果：返回写入的 chunk 数量，空文本返回 0。
        """
        cleaned_text = self.cleaner.clean(text, {"parser": "plain"})
        if not cleaned_text:
            return 0

        base_metadata = {
            "title": title,
            "source": source,
            "category": category,
            "tenant_id": tenant_id,
            "created_by": created_by,
            "document_id": document_id,
            "parser": "plain",
        }
        return await self._chunk_embed_store(
            text=cleaned_text,
            title=title,
            category=category,
            source=source,
            tenant_id=tenant_id,
            created_by=created_by,
            base_metadata=base_metadata,
        )

    async def _chunk_embed_store(
        self,
        text: str,
        title: str,
        category: str,
        source: str,
        tenant_id: str,
        created_by: str,
        base_metadata: dict[str, Any],
    ) -> int:
        """目的：生成 parent-child chunk，复用 child embedding 写入向量库和 ES。
        结果：成功返回总 chunk 数，失败时补偿删除已写入数据并抛出异常。
        """
        doc_id = self._build_doc_id(title=title, base_metadata=base_metadata)
        base = {
            **base_metadata,
            "doc_id": doc_id,
            "title": title,
            "source": source,
            "category": category,
            "tenant_id": tenant_id,
            "created_by": created_by,
        }
        chunks: list[TextChunk] = self.chunk_strategy.split(text, base)
        if not chunks:
            logger.warning("切分后无有效 chunk: title=%s", title)
            return 0

        child_chunks = [chunk for chunk in chunks if chunk.metadata.get("chunk_role") == "child"]
        embeddings = await self.embedding_service.embed_batch([chunk.text for chunk in child_chunks])
        child_embedding_map: dict[str, list[float]] = {}
        parent_embedding_map: dict[str, list[float]] = {}

        for chunk, embedding in zip(child_chunks, embeddings, strict=False):
            chunk_id = str(chunk.metadata.get("logical_chunk_id", ""))
            if chunk_id:
                child_embedding_map[chunk_id] = embedding
            parent_id = str(chunk.metadata.get("parent_id", ""))
            if parent_id:
                parent_embedding_map.setdefault(parent_id, embedding)

        es_documents: list[dict[str, Any]] = []
        vector_records: list[dict[str, Any]] = []
        try:
            for index, chunk in enumerate(chunks):
                metadata = dict(chunk.metadata)
                chunk_id = str(metadata.get("logical_chunk_id") or f"{doc_id}_chunk_{index}")
                parent_id = str(metadata.get("parent_id", ""))
                locator = self._build_locator(metadata)
                metadata.update(
                    {
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "logical_chunk_id": chunk_id,
                        "locator": locator,
                    }
                )
                chunk_role = metadata.get("chunk_role")
                chunk_embedding: list[float] | None = (
                    child_embedding_map.get(chunk_id)
                    if chunk_role == "child"
                    else parent_embedding_map.get(parent_id or chunk_id)
                )
                if chunk_embedding is None:
                    logger.warning(
                        "chunk 缺少可用 embedding，跳过写入: title=%s, chunk_id=%s, role=%s",
                        title,
                        chunk_id,
                        chunk_role,
                    )
                    continue

                vector_records.append(
                    {
                        "embedding": chunk_embedding,
                        "knowledge_id": doc_id,
                        "category": category,
                        "title": title,
                        "content": chunk.text,
                        "source": source,
                        "tenant_id": tenant_id,
                        "created_by": created_by,
                        "metadata_json": metadata,
                    }
                )

                if chunk_role == "child":
                    es_documents.append(
                        {
                            "doc_id": doc_id,
                            "parent_id": parent_id,
                            "chunk_id": chunk_id,
                            "title": title,
                            "heading_path": str(metadata.get("heading_path", "")),
                            "content": chunk.text,
                            "category": category,
                            "source": source,
                            "tenant_id": tenant_id,
                            "document_id": str(metadata.get("document_id", "")),
                            "locator": locator,
                            "metadata": metadata,
                        }
                    )

            self.vector_client.insert_knowledge_batch(vector_records)
            await self.lexical_retriever.index_documents(es_documents)
        except Exception:
            logger.exception("索引写入失败，开始补偿清理: title=%s, doc_id=%s", title, doc_id)
            try:
                self.vector_client.delete_knowledge(
                    source=source,
                    category=category,
                    doc_id=doc_id,
                    tenant_id=tenant_id,
                )
            except Exception as cleanup_exc:
                logger.warning("pgvector 补偿删除失败: doc_id=%s, error=%s", doc_id, cleanup_exc)
            try:
                await self.lexical_retriever.delete_document(
                    source=source,
                    category=category,
                    doc_id=doc_id,
                    tenant_id=tenant_id,
                )
            except Exception as cleanup_exc:
                logger.warning("ES 补偿删除失败: doc_id=%s, error=%s", doc_id, cleanup_exc)
            raise

        logger.info(
            "索引管道完成: title=%s, doc_id=%s, total=%d, child=%d",
            title,
            doc_id,
            len(chunks),
            len(es_documents),
        )
        return len(chunks)

    @staticmethod
    def _build_doc_id(title: str, base_metadata: dict[str, Any]) -> str:
        """目的：让同一来源、标题和分类的文档在重建时命中相同 doc_id。
        结果：返回短哈希形式的文档 ID。
        """
        scope = [
            str(base_metadata.get("source", "")),
            str(base_metadata.get("filename", "")),
            str(base_metadata.get("title", "")),
            str(title),
            str(base_metadata.get("category", "")),
        ]
        digest = hashlib.blake2s("||".join(scope).encode("utf-8"), digest_size=8).hexdigest()
        return f"doc_{digest}"

    @staticmethod
    def _build_locator(metadata: dict[str, Any]) -> str:
        """目的：把文件名、标题路径和页码等元数据压缩成可展示定位文本。
        结果：返回供证据展示和排障使用的 locator 字符串。
        """
        filename = str(metadata.get("filename", "")).strip()
        heading_path = str(metadata.get("heading_path", "")).strip()
        pages = metadata.get("pages")
        parts = [item for item in [filename, heading_path] if item]
        if isinstance(pages, int) and pages > 0:
            parts.append(f"pages={pages}")
        return " | ".join(parts)
