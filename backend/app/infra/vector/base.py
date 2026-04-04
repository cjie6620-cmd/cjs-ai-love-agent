from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase

from ...core.config import get_settings

_vector_engine: Engine | None = None


class VectorBase(DeclarativeBase):
    """pgvector 模型基类。"""


def get_vector_engine() -> Engine:
    """惰性获取 pgvector 引擎，首次调用时才真正建立连接池。"""
    global _vector_engine
    if _vector_engine is None:
        settings = get_settings()
        _vector_engine = create_engine(
            settings.vector_db_url,
            future=True,
            pool_pre_ping=True,
            # 向量库不可用时快速失败，避免自动建表长时间阻塞启动。
            connect_args={"connect_timeout": 3},
        )
    return _vector_engine
