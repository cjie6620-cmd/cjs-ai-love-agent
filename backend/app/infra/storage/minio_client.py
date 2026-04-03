from ...core.config import get_settings


class MinioClient:
    """文件上传模块的占位实现，后续再接真实 SDK。"""

    def __init__(self) -> None:
        self.settings = get_settings()
