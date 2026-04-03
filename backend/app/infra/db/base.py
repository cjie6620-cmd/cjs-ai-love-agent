from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from ...core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类。"""


settings = get_settings()
engine = create_engine(settings.mysql_url, future=True, pool_pre_ping=True)
