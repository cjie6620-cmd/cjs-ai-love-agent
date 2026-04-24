from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from llm.providers import xai_router as xai_router_module
from llm.providers.xai_router import XaiRouterProvider


class _FakeStream:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[object]:
        async def _generator() -> AsyncIterator[object]:
            for chunk in self._chunks:
                yield chunk

        return _generator()


def _content_chunk(text: str) -> object:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=text, tool_calls=None),
            )
        ]
    )


class _FakeAsyncOpenAI:
    def __init__(self, *args, **kwargs) -> None:
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create),
        )
        self._streams: list[_FakeStream] = []

    async def create(self, **kwargs) -> _FakeStream:
        return self._streams.pop(0)


@pytest.mark.asyncio
async def test_xai_router_generate_stream_yields_incrementally(monkeypatch) -> None:
    fake_client = _FakeAsyncOpenAI()
    fake_client._streams.append(
        _FakeStream([
            _content_chunk("你"),
            _content_chunk("好"),
            _content_chunk("呀"),
        ])
    )

    monkeypatch.setattr(xai_router_module, "AsyncOpenAI", lambda *args, **kwargs: fake_client)
    monkeypatch.setattr(
        xai_router_module,
        "get_langsmith_service",
        lambda: SimpleNamespace(wrap_openai_client=lambda client: client),
    )

    settings = SimpleNamespace(
        xai_api_key="xai-key",
        llm_base_url="https://example.com/v1",
        llm_model="gpt-5.4",
        mcp_amap_enabled=False,
        mcp_transport="streamable_http",
        amap_mcp_url="",
        amap_maps_api_key="",
        amap_mcp_headers={},
        tavily_api_key="",
        tokenizer_backend="char_estimate",
        hf_tokenizer_repo="",
    )

    provider = XaiRouterProvider(settings)

    chunks: list[str] = []
    async for chunk, _ in provider.generate_stream("system", "user"):
        chunks.append(chunk)

    assert chunks == ["你", "好", "呀"]
    assert provider._mcp_calls[-1].status == "skipped"
