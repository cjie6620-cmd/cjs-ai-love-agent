from __future__ import annotations

import pytest
import sys
import types

import core.startup_probe as startup_probe
from core.config import Settings


class _FakeResult:
    def __init__(self, *, scalar_value: object | None = None, rows: list[tuple[object, ...]] | None = None) -> None:
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar(self) -> object | None:
        return self._scalar_value

    def all(self) -> list[tuple[object, ...]]:
        return self._rows


class _FakeConnection:
    def __init__(self, *, has_vector_ext: bool, tables: set[str]) -> None:
        self._has_vector_ext = has_vector_ext
        self._tables = tables

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement) -> _FakeResult:
        sql = str(statement)
        if "SELECT 1" in sql:
            return _FakeResult(scalar_value=1)
        if "pg_extension" in sql:
            return _FakeResult(scalar_value=self._has_vector_ext)
        if "information_schema.tables" in sql:
            return _FakeResult(rows=[(table_name,) for table_name in sorted(self._tables)])
        raise AssertionError(f"unexpected SQL: {sql}")


class _FakeEngine:
    def __init__(self, *, has_vector_ext: bool, tables: set[str]) -> None:
        self._connection = _FakeConnection(has_vector_ext=has_vector_ext, tables=tables)

    def connect(self) -> _FakeConnection:
        return self._connection


@pytest.mark.parametrize(
    ("tables", "missing_table"),
    [
        ({"memory_embeddings", "style_sample_embeddings"}, "knowledge_embeddings"),
        ({"knowledge_embeddings", "style_sample_embeddings"}, "memory_embeddings"),
    ],
)
def test_probe_vector_db_fails_when_required_tables_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    tables: set[str],
    missing_table: str,
) -> None:
    settings = Settings(vector_db_url="postgresql+psycopg://user:pass@127.0.0.1:5432/test_db")
    monkeypatch.setattr(
        startup_probe,
        "get_vector_engine",
        lambda: _FakeEngine(has_vector_ext=True, tables=tables),
    )

    result = startup_probe.probe_vector_db(settings)

    assert result.ok is False
    assert result.name == "VectorDB"
    assert missing_table in result.detail


def test_probe_celery_worker_success(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(redis_url="redis://127.0.0.1:6379/0")

    class _FakeInspect:
        def ping(self) -> dict[str, dict[str, str]]:
            return {"celery@worker-1": {"ok": "pong"}}

    class _FakeControl:
        def inspect(self, timeout: int) -> _FakeInspect:
            assert timeout == 3
            return _FakeInspect()

    fake_worker = types.SimpleNamespace(celery_app=types.SimpleNamespace(control=_FakeControl()))
    monkeypatch.setitem(sys.modules, "agents.worker", fake_worker)

    result = startup_probe.probe_celery_worker(settings)

    assert result.ok is True
    assert result.name == "CeleryWorker"
    assert "celery@worker-1" in result.detail


def test_probe_celery_worker_fails_when_no_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(redis_url="redis://127.0.0.1:6379/0")

    class _FakeInspect:
        def ping(self) -> dict[str, dict[str, str]]:
            return {}

    class _FakeControl:
        def inspect(self, timeout: int) -> _FakeInspect:
            return _FakeInspect()

    fake_worker = types.SimpleNamespace(celery_app=types.SimpleNamespace(control=_FakeControl()))
    monkeypatch.setitem(sys.modules, "agents.worker", fake_worker)

    result = startup_probe.probe_celery_worker(settings)

    assert result.ok is False
    assert result.name == "CeleryWorker"
    assert "未检测到在线 worker" in result.detail


@pytest.mark.asyncio
async def test_probe_amap_mcp_fails_when_transport_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        mcp_amap_enabled=True,
        amap_mcp_url="http://127.0.0.1:3100/mcp",
        mcp_transport="streamable_http",
    )

    class _FailingTransport:
        def __init__(self, **_: object) -> None:
            self.closed = False

        async def list_tools(self) -> list[dict[str, object]]:
            raise RuntimeError("mcp down")

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(startup_probe, "McpStreamableHttpTransport", _FailingTransport)

    result = await startup_probe.probe_amap_mcp(settings)

    assert result.ok is False
    assert result.name == "AmapMCP"
    assert "mcp down" in result.detail
