from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from agents.workflows import langgraph_adapter as workflow_module
from agents.workflows.langgraph_adapter import CompanionGraphWorkflow
from contracts.chat import ChatRequest


class _FakePromptSpec:
    prompt_version = "chat.reply.v1"
    output_contract_version = "chat_reply_text.v2"

    def render_system_prompt(self) -> str:
        return "system"

    def render_user_prompt(self) -> str:
        return "user"


class _FakeLlmClient:
    async def generate_stream(self, system_prompt: str, user_prompt: str, *, history=None):
        del system_prompt, user_prompt, history
        for chunk in ("第一段", "第二段"):
            yield chunk, []

    def get_mcp_calls(self):
        return []

    def has_pending_tool_history(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_companion_workflow_stream_emits_multiple_token_events(monkeypatch) -> None:
    async def _fake_safety_check(state):
        return {"safety_level": "low"}

    async def _fake_recall_memory(state):
        return {}

    async def _fake_search_knowledge(state):
        return {}

    monkeypatch.setattr(
        workflow_module,
        "get_langsmith_service",
        lambda: SimpleNamespace(tracing_scope=lambda: nullcontext()),
    )
    monkeypatch.setattr(workflow_module, "safety_check", _fake_safety_check)
    monkeypatch.setattr(workflow_module, "build_advisor_draft", lambda state: {})
    monkeypatch.setattr(workflow_module, "recall_memory", _fake_recall_memory)
    monkeypatch.setattr(workflow_module, "search_knowledge", _fake_search_knowledge)
    monkeypatch.setattr(workflow_module, "build_reply_generation_context", lambda state: (_FakePromptSpec(), None))
    monkeypatch.setattr(workflow_module, "finalize_advisor", lambda state: {"advisor": None})
    monkeypatch.setattr(workflow_module, "output_guard", lambda state: {})

    runtime = SimpleNamespace(build_llm_client=lambda: _FakeLlmClient())
    workflow = CompanionGraphWorkflow(runtime=runtime)
    request = ChatRequest(
        session_id="session-test",
        user_id="user-test",
        message="你好",
        mode="companion",
    )

    events: list[str] = []
    async for payload in workflow.stream(request):
        events.append(payload)

    token_events = [item for item in events if item.startswith("event: token")]
    assert len(token_events) == 2
    assert '"content": "第一段"' in token_events[0]
    assert '"content": "第二段"' in token_events[1]
    assert any(item.startswith("event: done") for item in events)
