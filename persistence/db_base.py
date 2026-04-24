import logging
import re

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import get_settings

# 本模块日志器，统一走项目日志链路
logger = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _mask_db_url(url: str) -> str:
    """对数据库 URL 中的密码做脱敏处理，避免日志泄露敏感信息。"""
    # 匹配形如 scheme://user:password@host 的部分并把密码替换为 ***
    return re.sub(r"(://[^:/@]+:)[^@]*(@)", r"\1***\2", url)


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类。
    
    目的：封装SQLAlchemy 模型基类相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """


def get_engine() -> Engine:
    """惰性获取数据库引擎，首次调用时才真正建立连接池。
    
    目的：获取惰性获取数据库引擎，首次调用时才真正建立连接池。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, object]
        if settings.mysql_url.startswith("sqlite"):
            # 测试环境常用 SQLite，本参数用于允许跨线程访问同一个连接。
            connect_args = {"check_same_thread": False}
        else:
            # 本地经常只起一部分基础设施，这里缩短连接/读写超时，避免 MySQL 未启动时
            # connect() 在 Windows 下走 SYN 重试阻塞 ~21 秒，拖垮线程池造成整站假死。
            connect_args = {
                "connect_timeout": 2,
                "read_timeout": 5,
                "write_timeout": 5,
            }

        _engine = create_engine(
            settings.mysql_url,
            future=True,
            pool_pre_ping=True,
            # 限制池阻塞时间，池满时最多等 1 秒即抛错降级，而不是让请求一直挂起。
            pool_timeout=1,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """统一管理数据库会话工厂，避免业务代码重复创建 Session。
    
    目的：获取统一管理数据库会话工厂，避免业务代码重复创建 Session。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
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
    """测试切换数据库地址时，显式清理已缓存的引擎和会话工厂。

    目的：执行测试切换数据库地址时，显式清理已缓存的引擎和会话工厂相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def initialize_database() -> bool:
    """在应用启动阶段主动探测 MySQL 连通性，并以统一格式输出日志。

    目的：
        - 与 Redis / MinIO / LangGraph Checkpointer 保持一致的启动日志风格，
          便于运维在启动阶段一眼判断数据库是否可用。
        - 连接失败时不抛出异常，仅打 WARN 日志进入降级模式，避免因 MySQL
          不可用导致整个 FastAPI 进程启动失败。

    返回：
        bool: True 表示探测成功，False 表示连接失败已降级。
    """
    settings = get_settings()
    masked_url = _mask_db_url(settings.mysql_url)
    try:
        engine = get_engine()
        # 使用轻量 SQL 校验连通性；对 MySQL / SQLite 均兼容。
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("MySQL 数据库初始化成功: url=%s", masked_url)
        return True
    except SQLAlchemyError as exc:
        # 常见失败：网络超时、端口未开放、账号密码错误、数据库不存在等。
        logger.warning("MySQL 数据库初始化失败，持久化相关功能将降级: url=%s, 原因=%s", masked_url, exc)
        return False
    except Exception as exc:  # pragma: no cover - 兜底防御
        logger.warning("MySQL 数据库初始化异常，持久化相关功能将降级: url=%s, 原因=%s", masked_url, exc)
        return False
