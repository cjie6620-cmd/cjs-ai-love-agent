"""RAG 知识检索增强生成模块：提供向量存储、文档分块、检索和融合的完整实现。

目的：作为 rag 包的一级入口，统一导出 RAG 服务的核心接口 RagService，
使上层应用可以通过 from rag import RagService 方式调用知识检索功能，
屏蔽向量存储、嵌入生成、检索融合等底层实现细节。
结果：导出 RagService 类供外部使用。
"""

from .rag_service import RagService

__all__ = ["RagService"]
