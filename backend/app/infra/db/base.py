from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ...core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类。"""


def get_engine() -> Engine:
    """惰性获取数据库引擎，首次调用时才真正建立连接池。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, object]
        if settings.mysql_url.startswith("sqlite"):
            # 测试环境常用 SQLite，本参数用于允许跨线程访问同一个连接。
            connect_args = {"check_same_thread": False}
        else:
            # 本地经常只起一部分基础设施，这里缩短连接超时，避免启动卡很久。
            connect_args = {"connect_timeout": 3}

        _engine = create_engine(
            settings.mysql_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """统一管理数据库会话工厂，避免业务代码重复创建 Session。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


def reset_database_engine() -> None:
    """测试切换数据库地址时，显式清理已缓存的引擎和会话工厂。"""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
