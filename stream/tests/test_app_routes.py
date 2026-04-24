# -*- coding: utf-8 -*-
"""流式路由测试模块：验证流式聊天接口和健康检查端点的功能正确性。

目的：为流式路由功能提供测试，包括健康检查端点测试和流式聊天路由测试。
结果：验证 /health 和 /chat/stream 端点返回正确状态和 SSE 格式响应。

Author: AI-Love Team
Version: 0.2.0
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app as app_module
from app import app
from contracts.chat import ChatRequest, ChatResponse, ChatTrace
from core.config import get_settings


class _FakeRedisService:
    """模拟 Redis 限流服务：用于测试环境替代真实 Redis。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def __init__(self, allowed: bool = True) -> None:
        """初始化模拟 Redis 服务。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.allowed = allowed

    def check_rate_limit(self, key: str) -> bool:
        """检查请求频率是否超限。

        目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        return self.allowed


class _FakeAgentService:
    """模拟 Agent 服务：用于测试环境替代真实 Agent 服务。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    async def reply(self, request: ChatRequest) -> ChatResponse:
        """模拟同步回复方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return ChatResponse(
            reply=f"echo:{request.message}",
            mode=request.mode,
            trace=ChatTrace(safety_level="low"),
            advisor=None,
        )

    async def stream_reply(self, request: ChatRequest) -> AsyncIterator[str]:
        """模拟流式回复方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        yield 'event: token\ndata: {"content":"你"}\n\n'
        yield 'event: done\ndata: {"reply":"你好","mode":"companion","trace":{"memory_hits":[],"knowledge_hits":[],"retrieval_query":"","safety_level":"low","mcp_calls":[]},"advisor":null}\n\n'

    def list_conversations(self, user_id: str):
        """模拟获取会话列表方法。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return {"user_id": user_id, "conversations": []}

    async def list_conversations_async(self, user_id: str):
        """模拟异步获取会话列表方法。"""
        return {"user_id": user_id, "conversations": []}

    def shutdown(self) -> None:
        """模拟服务关闭方法。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        return None


def _prepare_test_app(monkeypatch) -> None:
    async def _fake_initialize_graph_resources() -> None:
        return None

    async def _fake_shutdown_graph_resources() -> None:
        return None

    async def _fake_run_startup_probes(_settings) -> list[object]:
        return []

    monkeypatch.setenv("LANGGRAPH_USE_CHECKPOINTER", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(
        app_module,
        "initialize_graph_resources",
        _fake_initialize_graph_resources,
    )
    monkeypatch.setattr(
        app_module,
        "shutdown_graph_resources",
        _fake_shutdown_graph_resources,
    )
    monkeypatch.setattr(app_module, "run_startup_probes", _fake_run_startup_probes)
    app.state.container = SimpleNamespace(
        redis_service=_FakeRedisService(),
        agent_service=_FakeAgentService(),
    )
    app.state.startup_probe_results = []
    app.state.startup_probe_summary = "success=0/0, failed=-"


def test_health_route_returns_ok(monkeypatch) -> None:
    """测试健康检查路由返回正确状态。

    目的：验证 /health 端点能够正确响应，返回服务健康状态。
    结果：HTTP 状态码为 200，响应包含 status="ok" 和 service="ai-love"。
    """
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "ai-love"


def test_health_route_includes_startup_probe_summary(monkeypatch) -> None:
    """测试健康检查路由返回启动探活结果。"""
    _prepare_test_app(monkeypatch)
    with TestClient(app) as client:
        app.state.startup_probe_summary = "success=4/6, failed=Redis,MinIO"
        app.state.startup_probe_results = [
            {
                "name": "Redis",
                "status": "fail",
                "endpoint": "redis://:***@127.0.0.1:6379/0",
                "detail": "ConnectionError: timeout",
            }
        ]
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["summary"] == "success=4/6, failed=Redis,MinIO"
    assert payload["dependencies"][0]["name"] == "Redis"
    assert payload["dependencies"][0]["status"] == "fail"


def test_chat_stream_route_returns_sse(monkeypatch) -> None:
    """测试流式聊天路由返回 SSE 格式响应。

    目的：验证 /chat/stream 端点能够正确处理聊天请求并返回 SSE 流式响应。
    结果：HTTP 状态码为 200，Content-Type 包含 "text/event-stream"，
    响应体包含 "event: token" 和 "event: done" 事件。
    """
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": "session-test",
                "user_id": "user-test",
                "message": "你好",
                "mode": "companion",
            },
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: token" in response.text
    assert "event: done" in response.text


def test_chat_conversations_route_returns_history(monkeypatch) -> None:
    """测试会话历史路由能够正常返回响应。"""
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/chat/conversations", params={"user_id": "user-test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "user-test"
    assert payload["conversations"] == []
