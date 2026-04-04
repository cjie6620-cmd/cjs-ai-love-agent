import logging

from sqlalchemy.exc import SQLAlchemyError

from ...core.config import get_settings
from . import models  # noqa: F401
from .base import Base, get_engine

logger = logging.getLogger(__name__)


def initialize_mysql_tables() -> None:
    """启动时自动补齐 MySQL 业务表，减少本地联调手动建表成本。"""
    settings = get_settings()
    if not settings.db_auto_create_tables:
        logger.info("MySQL 自动建表已关闭，跳过初始化。")
        return

    try:
        Base.metadata.create_all(bind=get_engine())
        logger.info("MySQL 业务表检查完成，如缺表已自动创建。")
    except SQLAlchemyError as exc:
        # 这里不阻塞服务启动，避免本地只联调模型接口时被数据库拖住。
        logger.warning("MySQL 自动建表失败，将继续启动服务: %s", exc)
