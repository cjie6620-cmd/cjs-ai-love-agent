from ...core.config import get_settings


class PgVectorClient:
    """当前只保留连接配置入口，避免业务层直接依赖底层存储。"""

    def __init__(self) -> None:
        self.settings = get_settings()
