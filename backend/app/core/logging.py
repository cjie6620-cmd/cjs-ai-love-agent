import logging


def setup_logging() -> None:
    """先使用最小日志配置，后续再统一接入结构化日志和链路追踪。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
