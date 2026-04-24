"""向量存储模块：提供向量数据库的客户端实现和模型定义。

目的：作为 vector_store 子包的入口，统一导出向量存储客户端 PgVectorClient，
使 RAG 系统可以将嵌入向量持久化存储到 PostgreSQL/PgVector 数据库，
支持高效的相似度检索和元数据过滤。
"""

from .pgvector_client import PgVectorClient

__all__ = ["PgVectorClient"]
