"""LLM 模块：提供统一的大语言模型调用接口。"""

from __future__ import annotations

__all__ = [
    "build_llm_provider",
    "LlmClient",
    "BaseLLmProvider",
    "XaiRouterProvider",
    "DeepseekMcpProvider",
]


def __getattr__(name: str):
    """目的：按需延迟加载目标对象，减少模块初始化阶段的耦合。
    结果：命中合法名称时返回对应对象，否则抛出 AttributeError。
    """
    if name == "build_llm_provider":
        from llm.factory import build_llm_provider

        return build_llm_provider
    if name == "LlmClient":
        from llm.client import LlmClient

        return LlmClient
    if name == "BaseLLmProvider":
        from llm.providers.base import BaseLLmProvider

        return BaseLLmProvider
    if name == "XaiRouterProvider":
        from llm.providers.xai_router import XaiRouterProvider

        return XaiRouterProvider
    if name == "DeepseekMcpProvider":
        from llm.providers.openai_remote import DeepseekMcpProvider

        return DeepseekMcpProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
