# -*- coding: utf-8 -*-
"""流式路由测试模块：验证流式聊天接口和健康检查端点的功能正确性。

目的：为流式路由功能提供测试，包括健康检查端点测试和流式聊天路由测试。
结果：验证 /health 和 /chat/stream 端点返回正确状态和 SSE 格式响应。

Author: AI-Love Team
Version: 0.2.0
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app as app_module
import api.deps as deps_module
from agents.stream_registry import StreamTaskConflictError
from app import app
from contracts.chat import CancelStreamResponse, ChatRequest, ChatResponse, ChatTrace
from core.config import get_settings
from security.auth import CurrentUser


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
        self._quota_counts: dict[str, int] = {}

    def check_rate_limit(self, key: str) -> bool:
        """检查请求频率是否超限。

        目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        return self.allowed

    def increment_with_ttl(self, key: str, *, ttl: int) -> int | None:
        """模拟访客额度计数。"""
        if not self.allowed:
            return None
        current = self._quota_counts.get(key, 0) + 1
        self._quota_counts[key] = current
        return current


class _FakeAgentService:
    """模拟 Agent 服务：用于测试环境替代真实 Agent 服务。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def __init__(self) -> None:
        """初始化模拟 Agent 服务。"""
        self._active_streams: dict[str, tuple[str, str]] = {}

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

    async def start_stream(self, stream_id: str, request: ChatRequest) -> asyncio.Queue[str | None]:
        """模拟后台流任务启动。"""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._active_streams[stream_id] = (request.user_id, request.session_id)
        await queue.put('event: token\ndata: {"content":"你"}\n\n')
        await queue.put('event: done\ndata: {"reply":"你好","mode":"companion","trace":{"memory_hits":[],"knowledge_hits":[],"retrieval_query":"","safety_level":"low","mcp_calls":[]},"advisor":null}\n\n')
        await queue.put(None)
        return queue

    async def remove_stream_subscriber(
        self,
        stream_id: str,
        subscriber: asyncio.Queue[str | None],
    ) -> None:
        """模拟移除订阅者。"""
        del subscriber
        self._active_streams.pop(stream_id, None)

    async def cancel_stream(self, stream_id: str, user_id: str) -> CancelStreamResponse:
        """模拟取消流任务。"""
        active = self._active_streams.get(stream_id)
        if active is None or active[0] != user_id:
            return CancelStreamResponse(stream_id=stream_id, status="not_found", accepted=False)
        self._active_streams.pop(stream_id, None)
        return CancelStreamResponse(stream_id=stream_id, status="cancelled", accepted=False)

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


class _FakeMemorySettingsRepository:
    def __init__(self) -> None:
        self.enabled = False

    def get_settings(self, user_id: str) -> dict[str, bool]:
        del user_id
        return {"memory_enabled": self.enabled}

    def set_enabled(self, user_id: str, enabled: bool) -> dict[str, bool]:
        del user_id
        self.enabled = enabled
        return {"memory_enabled": self.enabled}


class _FakeVectorClient:
    def __init__(self) -> None:
        self.items = [
            {
                "id": "mem-001",
                "memory_type": "preference",
                "canonical_key": "preference:reply_length",
                "content": "用户喜欢简洁回复",
                "importance_score": 0.9,
                "confidence": 0.95,
                "status": "active",
                "metadata_json": {},
                "created_at": None,
                "last_seen_at": None,
                "updated_at": None,
            }
        ]

    def list_user_memories(self, *, user_id: str, limit: int, offset: int):
        del user_id
        return self.items[offset:offset + limit]

    def count_user_memories(self, *, user_id: str) -> int:
        del user_id
        return len(self.items)

    def soft_delete_memory(self, *, user_id: str, record_id: str) -> int:
        del user_id
        before = len(self.items)
        self.items = [item for item in self.items if item["id"] != record_id]
        return before - len(self.items)

    def soft_delete_user_memories(self, *, user_id: str) -> int:
        del user_id
        count = len(self.items)
        self.items = []
        return count


class _FakeMemoryManager:
    def __init__(self) -> None:
        self.vector_client = _FakeVectorClient()


class _FakeMemoryAuditRepository:
    def record(self, **kwargs) -> str:
        del kwargs
        return "audit-001"


def _prepare_test_app(monkeypatch, *, redis_service: _FakeRedisService | None = None) -> None:
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
        settings=get_settings(),
        redis_service=redis_service or _FakeRedisService(),
        agent_service=_FakeAgentService(),
        memory_settings_repository=_FakeMemorySettingsRepository(),
        memory_audit_repository=_FakeMemoryAuditRepository(),
        memory_manager=_FakeMemoryManager(),
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
    assert payload["code"] == 200
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "ai-love"


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
    assert payload["code"] == 200
    assert payload["data"]["status"] == "degraded"
    assert payload["data"]["summary"] == "success=4/6, failed=Redis,MinIO"
    assert payload["data"]["dependencies"][0]["name"] == "Redis"
    assert payload["data"]["dependencies"][0]["status"] == "fail"


def test_chat_stream_route_returns_sse(monkeypatch) -> None:
    """测试流式聊天路由返回 SSE 格式响应。

    目的：验证 /chat/stream 端点能够正确处理聊天请求并返回 SSE 流式响应。
    结果：HTTP 状态码为 200，Content-Type 包含 "text/event-stream"，
    响应体包含 "event: token" 和 "event: done" 事件。
    """
    monkeypatch.setenv("GUEST_DAILY_MESSAGE_LIMIT", "2")
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
    assert response.headers["X-Stream-Id"]
    assert response.headers["X-Guest-Identity"].startswith("guest:")
    assert response.headers["X-Guest-Limit"] == "2"
    assert response.headers["X-Guest-Remaining"] == "1"
    assert response.headers["X-Guest-Count"] == "1"
    assert response.headers["X-Guest-Quota-Reason"] == "allowed"
    assert "event: token" in response.text
    assert "event: done" in response.text


def test_cancel_stream_route_returns_not_found_for_unknown_stream(monkeypatch) -> None:
    """测试取消未知流任务时返回幂等 not_found。"""
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.post("/chat/streams/stream-missing/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["stream_id"] == "stream-missing"
    assert payload["data"]["status"] == "not_found"
    assert payload["data"]["accepted"] is False


def test_chat_stream_route_returns_conflict_when_session_is_busy(monkeypatch) -> None:
    """测试同一会话已有后台流任务时返回 409。"""
    _prepare_test_app(monkeypatch)

    async def _raise_conflict(stream_id: str, request: ChatRequest):
        del stream_id, request
        raise StreamTaskConflictError(stream_id="stream-existing", status="running")

    app.state.container.agent_service.start_stream = _raise_conflict

    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": "session-test",
                "user_id": "ignored",
                "message": "你好",
                "mode": "companion",
            },
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["data"]["error_code"] == "STREAM_ALREADY_RUNNING"
    assert payload["data"]["stream_id"] == "stream-existing"


def test_chat_conversations_route_returns_history(monkeypatch) -> None:
    """测试会话历史路由能够正常返回响应。"""
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/chat/conversations", params={"user_id": "user-test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["user_id"].startswith("guest:")
    assert payload["data"]["conversations"] == []


def test_guest_quota_is_enforced_with_signed_cookie_identity(monkeypatch) -> None:
    """测试未登录访客按签名 Cookie 累计额度，不再信任 Header。"""
    monkeypatch.setenv("GUEST_DAILY_MESSAGE_LIMIT", "2")
    redis_service = _FakeRedisService()
    _prepare_test_app(monkeypatch, redis_service=redis_service)

    with TestClient(app) as client:
        first = client.post(
            "/chat/stream",
            json={
                "session_id": "session-test",
                "user_id": "ignored",
                "message": "第一句",
                "mode": "companion",
            },
        )
        second = client.post(
            "/chat/stream",
            json={
                "session_id": "session-test",
                "user_id": "ignored",
                "message": "第二句",
                "mode": "companion",
            },
        )
        third = client.post(
            "/chat/stream",
            json={
                "session_id": "session-test",
                "user_id": "ignored",
                "message": "第三句",
                "mode": "companion",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 401
    assert first.headers["X-Guest-Limit"] == "2"
    assert second.headers["X-Guest-Remaining"] == "0"
    assert third.headers["X-Guest-Quota-Reason"] == "limit_exceeded"
    assert third.json()["code"] == 401
    assert third.json()["data"]["error_code"] == "LOGIN_REQUIRED"
    assert third.json()["data"]["remaining"] == 0
    assert third.json()["data"]["limit"] == 2


def test_chat_reply_guest_quota_limit_one_blocks_second_request(monkeypatch) -> None:
    """测试 /chat/reply 在 limit=1 时第二次请求直接返回登录要求。"""
    monkeypatch.setenv("GUEST_DAILY_MESSAGE_LIMIT", "1")
    redis_service = _FakeRedisService()
    _prepare_test_app(monkeypatch, redis_service=redis_service)

    with TestClient(app) as client:
        first = client.post(
            "/chat/reply",
            json={
                "session_id": "reply-session-1",
                "user_id": "ignored",
                "message": "第一句",
                "mode": "companion",
            },
        )
        second = client.post(
            "/chat/reply",
            json={
                "session_id": "reply-session-2",
                "user_id": "ignored",
                "message": "第二句",
                "mode": "companion",
            },
        )

    assert first.status_code == 200
    assert first.headers["X-Guest-Limit"] == "1"
    assert first.headers["X-Guest-Remaining"] == "0"
    assert second.status_code == 401
    assert second.headers["X-Guest-Limit"] == "1"
    assert second.headers["X-Guest-Quota-Reason"] == "limit_exceeded"
    assert second.json()["code"] == 401
    assert second.json()["data"]["error_code"] == "LOGIN_REQUIRED"
    assert second.json()["data"]["limit"] == 1


def test_authenticated_request_skips_guest_quota(monkeypatch) -> None:
    """测试已登录用户请求不会走匿名访客额度。"""
    monkeypatch.setenv("GUEST_DAILY_MESSAGE_LIMIT", "1")
    redis_service = _FakeRedisService()
    _prepare_test_app(monkeypatch, redis_service=redis_service)

    def _fake_current_user(request, container):
        return CurrentUser(
            id="user-authenticated",
            tenant_id="default",
            external_user_id="user-authenticated",
            nickname="已登录用户",
            avatar_url="",
            roles=["user"],
            permissions=[],
        )

    monkeypatch.setattr(deps_module, "get_optional_current_user", _fake_current_user)

    with TestClient(app) as client:
        first = client.post(
            "/chat/reply",
            json={
                "session_id": "auth-session-1",
                "user_id": "ignored",
                "message": "第一句",
                "mode": "companion",
            },
        )
        second = client.post(
            "/chat/reply",
            json={
                "session_id": "auth-session-2",
                "user_id": "ignored",
                "message": "第二句",
                "mode": "companion",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Guest-Identity"] == "authenticated"
    assert "X-Guest-Limit" not in first.headers
    assert redis_service._quota_counts == {}


def test_tampered_guest_cookie_is_reset(monkeypatch) -> None:
    """测试篡改访客 Cookie 后，后端会生成新的匿名身份。"""
    _prepare_test_app(monkeypatch)
    forged_guest_id = "6d4a8d36-8d53-4f8f-bbd8-8ca8e2fb4fd0"

    with TestClient(app) as client:
        response = client.get(
            "/chat/conversations",
            headers={"Cookie": f"{deps_module.GUEST_COOKIE_NAME}={forged_guest_id}.9999999999.bad"},
        )

    assert response.status_code == 200
    assert response.headers["X-Guest-Identity"].startswith("guest:")
    assert response.headers["X-Guest-Identity"] != f"guest:{forged_guest_id}"
    assert deps_module.GUEST_COOKIE_NAME in response.headers["set-cookie"]


def test_public_knowledge_management_routes_are_removed(monkeypatch) -> None:
    """测试旧公开知识库管理入口不再存在。"""
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.post("/knowledge/text", json={"title": "x", "text": "y"})

    assert response.status_code == 404


def test_admin_route_requires_login(monkeypatch) -> None:
    """测试未登录访问后台返回 401。"""
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/admin/me")

    assert response.status_code == 401


def test_admin_route_rejects_user_without_permission(monkeypatch) -> None:
    """测试普通用户没有 admin:access 时返回 403。"""
    _prepare_test_app(monkeypatch)

    def _fake_current_user(request, container):
        return CurrentUser(
            id="user-normal",
            tenant_id="default",
            external_user_id="normal",
            nickname="普通用户",
            avatar_url="",
            roles=["user"],
            permissions=[],
        )

    monkeypatch.setattr(deps_module, "get_optional_current_user", _fake_current_user)

    with TestClient(app) as client:
        response = client.get("/admin/me")

    assert response.status_code == 403


def test_admin_route_allows_admin_permission(monkeypatch) -> None:
    """测试具备 admin:access 的用户可以访问后台当前用户信息。"""
    _prepare_test_app(monkeypatch)

    def _fake_current_user(request, container):
        return CurrentUser(
            id="user-admin",
            tenant_id="default",
            external_user_id="admin",
            nickname="管理员",
            avatar_url="",
            roles=["admin"],
            permissions=["admin:access"],
        )

    monkeypatch.setattr(deps_module, "get_optional_current_user", _fake_current_user)

    with TestClient(app) as client:
        response = client.get("/admin/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["user"]["id"] == "user-admin"
    assert payload["data"]["permissions"] == ["admin:access"]


def test_memory_route_requires_login(monkeypatch) -> None:
    """测试长期记忆接口必须登录。"""
    _prepare_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.get("/memory/settings")

    assert response.status_code == 401


def test_memory_routes_manage_current_user_memory(monkeypatch) -> None:
    """测试当前用户可以开关、查看、删除和清空自己的长期记忆。"""
    _prepare_test_app(monkeypatch)

    def _fake_current_user(request, container):
        del request, container
        return CurrentUser(
            id="user-authenticated",
            tenant_id="default",
            external_user_id="user-authenticated",
            nickname="已登录用户",
            avatar_url="",
            roles=["user"],
            permissions=[],
        )

    monkeypatch.setattr(deps_module, "get_optional_current_user", _fake_current_user)

    with TestClient(app) as client:
        settings_before = client.get("/memory/settings")
        settings_after = client.put("/memory/settings", json={"memory_enabled": True})
        items = client.get("/memory/items")
        deleted = client.delete("/memory/items/mem-001")
        cleared = client.delete("/memory/items")

    assert settings_before.status_code == 200
    assert settings_before.json()["data"]["memory_enabled"] is False
    assert settings_after.json()["data"]["memory_enabled"] is True
    assert items.json()["data"]["total"] == 1
    assert items.json()["data"]["items"][0]["content"] == "用户喜欢简洁回复"
    assert deleted.json()["data"]["deleted_count"] == 1
    assert cleared.json()["data"]["deleted_count"] == 0


def test_startup_logs_effective_guest_quota(monkeypatch, capsys) -> None:
    """测试启动时会打印当前生效的访客额度配置。"""
    monkeypatch.setenv("GUEST_DAILY_MESSAGE_LIMIT", "1")
    _prepare_test_app(monkeypatch)

    with TestClient(app):
        pass
    captured = capsys.readouterr()

    assert "guest_daily_message_limit=1" in captured.err
