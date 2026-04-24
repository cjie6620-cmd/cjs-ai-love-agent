"""LLM Provider 工厂。"""

from __future__ import annotations

import logging

from core.config import Settings
from llm.providers import LlmProvider

logger = logging.getLogger(__name__)


def build_llm_provider(settings: Settings) -> LlmProvider:
    """根据配置构建具体 Provider。
    
    目的：构建根据配置构建具体 Provider所需的数据或对象。
    结果：返回后续流程可直接消费的构建结果。
    """
    from llm.providers.openai_remote import DeepseekMcpProvider
    from llm.providers.xai_router import XaiRouterProvider

    if settings.llm_provider == "openai_remote_mcp":
        logger.info("使用 DeepseekMcpProvider（DeepSeek API + Function Calling）")
        return DeepseekMcpProvider(settings)

    logger.info("使用 XaiRouterProvider（Chat Completions API）")
    return XaiRouterProvider(settings)
