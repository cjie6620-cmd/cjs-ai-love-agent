from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import get_settings

_vector_engine: Engine | None = None
_vector_session_factory: sessionmaker[Session] | None = None


class VectorBase(DeclarativeBase):
    """目的：为向量存储相关 ORM 模型提供统一的声明式基类，集中管理映射元数据。
    结果：`MemoryEmbedding`、`KnowledgeEmbedding`、`StyleSampleEmbedding` 等模型可以基于同一套 SQLAlchemy 元信息完成建表和映射。
    """


def get_vector_engine() -> Engine:
    """目的：统一创建并缓存 pgvector 数据库引擎，避免业务侧重复初始化连接池。
    结果：返回可复用的 `Engine` 实例，供会话工厂和数据访问层共享使用。
    """
    global _vector_engine
    if _vector_engine is None:
        settings = get_settings()
        _vector_engine = create_engine(
            settings.vector_db_url,
            future=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            # 外部向量库缺失时要尽快降级，避免启动被长时间阻塞。
            connect_args={"connect_timeout": 3},
        )
    return _vector_engine


def get_vector_session_factory() -> sessionmaker[Session]:
    """目的：基于统一的 pgvector 引擎创建并缓存会话工厂，收敛 Session 配置入口。
    结果：返回可重复使用的 `sessionmaker`，调用方可以稳定创建数据库会话。
    """
    global _vector_session_factory
    if _vector_session_factory is None:
        _vector_session_factory = sessionmaker(
            bind=get_vector_engine(),
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )
    return _vector_session_factory


def reset_vector_engine() -> None:
    """目的：在测试或配置切换场景下释放旧连接并清空缓存，避免继续复用过期数据库连接。
    结果：已缓存的 `Engine` 和 `sessionmaker` 被重置，下次访问时会按最新配置重新创建。
    """
    global _vector_engine, _vector_session_factory
    if _vector_engine is not None:
        _vector_engine.dispose()
    _vector_engine = None
    _vector_session_factory = None
