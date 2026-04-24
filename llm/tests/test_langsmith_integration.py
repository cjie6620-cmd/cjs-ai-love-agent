from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm.providers.openai_remote import DeepseekMcpProvider
from observability import langsmith_service as langsmith_module
from observability.langsmith_service import LangSmithService


def test_langsmith_client_init_uses_supported_kwargs(monkeypatch) -> None:
    """验证 langsmith client init uses supported kwargs。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    captured: dict[str, object] = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(langsmith_module, "Client", _FakeClient)
    service = LangSmithService(
        SimpleNamespace(
            langsmith_enabled=True,
            langsmith_tracing=True,
            langsmith_api_key="ls-key",
            langsmith_endpoint="https://example.com",
            langsmith_workspace_id="ws-1",
            langsmith_project="ai-love",
            app_env="test",
        )
    )

    client = service.get_client()

    assert client is not None
    assert captured == {
        "api_key": "ls-key",
        "api_url": "https://example.com",
        "workspace_id": "ws-1",
    }


@pytest.mark.asyncio
async def test_deepseek_tool_tracking_never_uses_pending_status(monkeypatch) -> None:
    """验证 deepseek tool tracking never uses pending status。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    settings = SimpleNamespace(
        deepseek_api_key="key",
        deepseek_base_url="https://example.com/v1",
        deepseek_model="deepseek-chat",
        mcp_tavily_enabled=True,
        tavily_api_key="tvly-key",
        mcp_amap_enabled=False,
        amap_maps_api_key="",
        tokenizer_backend="char_estimate",
        hf_tokenizer_repo="",
        langsmith_enabled=False,
        langsmith_tracing=False,
        langsmith_api_key="",
        langsmith_endpoint="",
        langsmith_workspace_id="",
        langsmith_project="",
        app_env="test",
    )
    provider = DeepseekMcpProvider(settings)

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "results": [
                    {
                        "title": "标题",
                        "url": "https://example.com",
                        "content": "内容摘要",
                    }
                ]
            }

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: _FakeClient())

    result = await provider._call_mcp_tool("tavily_search", {"query": "LangSmith"})

    assert "标题" in result
    assert provider._mcp_calls
    assert all(call.status in {"success", "error", "skipped"} for call in provider._mcp_calls)
    assert provider._mcp_calls[-1].status == "success"
