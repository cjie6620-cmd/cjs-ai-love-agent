from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import llm.providers.base as base_module

from core.config import Settings
from llm.core.types import McpCallInfo
from llm.providers.base import BaseLLmProvider


class DummyProvider(BaseLLmProvider):
    """DummyProvider 测试桩实现。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    def __init__(self, settings: Settings, model_name: str) -> None:
        """初始化 DummyProvider 实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        super().__init__(settings)
        self._model_name = model_name

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[McpCallInfo]]:
        """执行 generate 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        raise NotImplementedError

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[tuple[str, list[McpCallInfo]]]:
        """执行 generate_stream 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if False:
            yield "", []
        raise NotImplementedError

    def _get_model_name(self) -> str:
        """获取目标资源或配置。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return self._model_name

    def _get_structured_client_options(self) -> dict[str, str]:
        """返回测试所需的最小 structured client 配置。"""
        return {
            "model": self._model_name,
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
        }


class FakeEncoder:
    """FakeEncoder 测试替身对象。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    def __init__(self, token_count: int) -> None:
        """初始化 FakeEncoder 实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.token_count = token_count

    def encode(self, text: str) -> list[int]:
        """执行 encode 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return [1] * self.token_count


class FakeTokenizer:
    """FakeTokenizer 测试替身对象。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    def __init__(self, token_count: int) -> None:
        """初始化 FakeTokenizer 实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.token_count = token_count

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        """执行 encode 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        del text, add_special_tokens
        return [1] * self.token_count


def _make_settings(**overrides: Any) -> Settings:
    """make settings 测试辅助方法。
    
    目的：为当前测试文件提供公共构造、准备或提取逻辑。
    结果：减少重复测试代码，提升测试可读性和维护性。
    """
    defaults: dict[str, Any] = {
        "llm_model": "gpt-5",
        "tokenizer_backend": "auto",
        "hf_tokenizer_repo": "",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def test_auto_backend_uses_tiktoken_for_gpt_models(monkeypatch) -> None:
    """验证 auto backend uses tiktoken for gpt models。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(_make_settings(), "gpt-5")

    monkeypatch.setattr(base_module, "_get_tiktoken_encoder", lambda: FakeEncoder(3))
    monkeypatch.setattr(base_module, "_load_hf_tokenizer", lambda repo_id: None)

    assert provider._resolve_tokenizer_backend() == "tiktoken"
    assert provider._count_tokens("hello world") == 3


def test_auto_backend_uses_huggingface_for_deepseek(monkeypatch) -> None:
    """验证 auto backend uses huggingface for deepseek。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(_make_settings(), "deepseek-chat")
    called: list[str] = []

    def fake_load(repo_id: str) -> FakeTokenizer:
        called.append(repo_id)
        return FakeTokenizer(5)

    monkeypatch.setattr(base_module, "_load_hf_tokenizer", fake_load)
    monkeypatch.setattr(base_module, "_get_tiktoken_encoder", lambda: None)

    assert provider._resolve_tokenizer_backend() == "huggingface"
    assert provider._count_tokens("你好，DeepSeek") == 5
    assert called == ["deepseek-ai/DeepSeek-V3"]


def test_auto_backend_uses_huggingface_for_qwen(monkeypatch) -> None:
    """验证 auto backend uses huggingface for qwen。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(_make_settings(), "qwen-plus")
    called: list[str] = []

    def fake_load(repo_id: str) -> FakeTokenizer:
        called.append(repo_id)
        return FakeTokenizer(4)

    monkeypatch.setattr(base_module, "_load_hf_tokenizer", fake_load)

    assert provider._count_tokens("你好，Qwen") == 4
    assert called == ["Qwen/Qwen2.5-7B-Instruct"]


def test_huggingface_init_failure_falls_back_to_char_estimate(monkeypatch) -> None:
    """验证 huggingface init failure falls back to char estimate。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(_make_settings(), "deepseek-chat")

    monkeypatch.setattr(base_module, "_load_hf_tokenizer", lambda repo_id: None)

    assert provider._count_tokens("abcdefghij") == 2


def test_explicit_huggingface_backend_overrides_auto(monkeypatch) -> None:
    """验证 explicit huggingface backend overrides auto。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(
        _make_settings(tokenizer_backend="huggingface", hf_tokenizer_repo="custom/repo"),
        "gpt-5",
    )
    called: list[str] = []

    def fake_load(repo_id: str) -> FakeTokenizer:
        called.append(repo_id)
        return FakeTokenizer(7)

    monkeypatch.setattr(base_module, "_load_hf_tokenizer", fake_load)
    monkeypatch.setattr(base_module, "_get_tiktoken_encoder", lambda: FakeEncoder(2))

    assert provider._resolve_tokenizer_backend() == "huggingface"
    assert provider._count_tokens("override") == 7
    assert called == ["custom/repo"]


def test_explicit_tiktoken_backend_overrides_auto(monkeypatch) -> None:
    """验证 explicit tiktoken backend overrides auto。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(_make_settings(tokenizer_backend="tiktoken"), "deepseek-chat")

    monkeypatch.setattr(base_module, "_get_tiktoken_encoder", lambda: FakeEncoder(6))
    monkeypatch.setattr(base_module, "_load_hf_tokenizer", lambda repo_id: FakeTokenizer(1))

    assert provider._resolve_tokenizer_backend() == "tiktoken"
    assert provider._count_tokens("override") == 6


def test_truncate_by_tokens_keeps_recent_messages_under_budget(monkeypatch) -> None:
    """验证 truncate by tokens keeps recent messages under budget。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = DummyProvider(_make_settings(), "deepseek-chat")

    monkeypatch.setattr(base_module, "_MAX_TOTAL_TOKENS", 70)
    monkeypatch.setattr(base_module, "_load_hf_tokenizer", lambda repo_id: FakeTokenizer(3))

    history = [
        {"role": "user", "content": "1 2 3"},
        {"role": "assistant", "content": "4 5 6"},
        {"role": "user", "content": "7 8 9"},
        {"role": "assistant", "content": "10 11 12"},
    ]

    trimmed = provider._truncate_by_tokens(history, "sys", "ask")

    assert trimmed == history[-2:]
