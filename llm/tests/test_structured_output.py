from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from contracts.chat import ChatReplyModel, MemoryDecision
from llm.providers.base import BaseLLmProvider
from prompt import PromptSection, PromptSpec


class _DummyProvider(BaseLLmProvider):
    """用于验证专用 structured path 的测试桩 Provider。"""

    def __init__(self) -> None:
        settings = SimpleNamespace(tokenizer_backend="char_estimate", hf_tokenizer_repo="")
        super().__init__(settings)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history=None,
    ) -> tuple[str, list]:
        del system_prompt, user_prompt, history
        return "", []

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history=None,
    ) -> AsyncIterator[tuple[str, list]]:
        del system_prompt, user_prompt, history
        if False:
            yield "", []

    def _get_model_name(self) -> str:
        return "dummy-model"

    def _get_structured_client_options(self) -> dict[str, str]:
        return {
            "model": "dummy-model",
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
        }


class _FakeStructuredRunnable:
    """模拟 with_structured_output 返回的 runnable。"""

    def __init__(self, payload: object, captured: dict[str, object]) -> None:
        self._payload = payload
        self._captured = captured

    async def ainvoke(self, messages: list[object]) -> object:
        self._captured["messages"] = messages
        return self._payload


class _FakeStructuredChatModel:
    """模拟 LangChain ChatOpenAI。"""

    def __init__(self, payload: object, captured: dict[str, object]) -> None:
        self._payload = payload
        self._captured = captured

    def with_structured_output(self, schema: type[object]) -> _FakeStructuredRunnable:
        self._captured["schema"] = schema
        return _FakeStructuredRunnable(self._payload, self._captured)


def _build_prompt_spec(name: str, output_schema_name: str) -> PromptSpec:
    return PromptSpec(
        name=name,
        prompt_version=f"{name}.v1",
        output_schema_name=output_schema_name,
        system_sections=[PromptSection(name="role", content="你是助手")],
        user_sections=[PromptSection(name="context", content="请完成任务")],
        fallback_policy="无法判断时保持保守。",
    )


@pytest.mark.asyncio
async def test_decide_memory_uses_dedicated_structured_output(monkeypatch) -> None:
    """memory.decide 应走专用 with_structured_output 链路。"""
    provider = _DummyProvider()
    captured: dict[str, object] = {}
    payload = {
        "should_store": True,
        "memory_type": "profile_summary",
        "memory_text": "用户冲突时容易先沉默。",
        "confidence": 0.88,
        "reason_code": "stable_profile",
    }
    monkeypatch.setattr(
        provider,
        "_build_structured_chat_model",
        lambda: _FakeStructuredChatModel(payload, captured),
    )

    result, _ = await provider.decide_memory(
        _build_prompt_spec("memory.decision", "MemoryDecision")
    )

    assert isinstance(result, MemoryDecision)
    assert result.should_store is True
    assert captured["schema"] is MemoryDecision
    assert captured["messages"]


@pytest.mark.asyncio
async def test_finalize_chat_reply_uses_pending_tool_history(monkeypatch) -> None:
    """工具终结 structured 输出应消费 provider 保存的 tool history。"""
    provider = _DummyProvider()
    provider._set_pending_tool_history(
        [
            {"role": "user", "content": "北京今天天气怎么样"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "amap_weather"}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "晴，24 度"},
        ]
    )

    captured: dict[str, object] = {}
    payload = {
        "reply_text": "北京今天晴，24 度，适合轻装出门。",
        "intent": "advice",
        "tone": "direct",
        "grounded_by_knowledge": False,
        "used_memory": False,
        "needs_followup": False,
        "fallback_reason": "",
        "safety_notes": [],
        "used_evidence_ids": [],
    }
    monkeypatch.setattr(
        provider,
        "_build_structured_chat_model",
        lambda: _FakeStructuredChatModel(payload, captured),
    )

    result, _ = await provider.finalize_chat_reply(
        _build_prompt_spec("chat.reply.tool_final", "ChatReplyModel")
    )

    assert isinstance(result, ChatReplyModel)
    assert result.reply_text.startswith("北京今天晴")
    assert captured["schema"] is ChatReplyModel
    rendered_messages = captured["messages"]
    assert rendered_messages
    assert any("工具结果" in str(getattr(message, "content", "")) for message in rendered_messages)
