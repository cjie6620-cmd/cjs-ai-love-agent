"""嵌入向量模块：提供文本到向量 embedding 的转换服务。

目的：作为 embeddings 子包的入口，统一导出嵌入服务接口 EmbeddingService，
使 RAG 流程可以将文本内容转换为高维向量表示，
支持语义相似度检索和向量数据库存储。
结果：导出 EmbeddingService 类。
"""

from .service import EmbeddingService

__all__ = ["EmbeddingService"]
