from celery import Celery

from ..core.config import get_settings

settings = get_settings()

# 这里单独保留 Celery 入口，后续风格分析、记忆整理、索引构建都可以挂到这里。
celery_app = Celery("ai_love", broker=settings.redis_url, backend=settings.redis_url)
