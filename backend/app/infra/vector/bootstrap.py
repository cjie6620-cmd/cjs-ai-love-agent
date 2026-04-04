import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...core.config import get_settings
from . import models  # noqa: F401
from .base import VectorBase, get_vector_engine

logger = logging.getLogger(__name__)


def initialize_vector_tables() -> None:
    """启动时自动创建 pgvector 扩展和向量表，方便本地直接联调。"""
    settings = get_settings()
    if not settings.vector_auto_create_tables:
        logger.info("pgvector 自动建表已关闭，跳过初始化。")
        return

    try:
        with get_vector_engine().begin() as connection:
            # 先确保安装了扩展，否则 Vector 列无法落表。
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            VectorBase.metadata.create_all(bind=connection)
        logger.info("pgvector 表检查完成，如缺表已自动创建。")
    except SQLAlchemyError as exc:
        # 这里不阻塞服务启动，避免没有 PostgreSQL 时无法本地开发其它模块。
        logger.warning("pgvector 自动建表失败，将继续启动服务: %s", exc)
