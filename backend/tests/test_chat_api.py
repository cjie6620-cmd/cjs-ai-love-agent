from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.infra.db.base import reset_database_engine
from app.main import app


@pytest.fixture()
def sqlite_chat_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """聊天接口测试改用临时 SQLite，避免依赖本地 MySQL。"""
    database_path = tmp_path / "chat-test.db"
    monkeypatch.setenv("MYSQL_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("DB_AUTO_CREATE_TABLES", "true")

    get_settings.cache_clear()
    reset_database_engine()
    yield
    reset_database_engine()
    get_settings.cache_clear()


def test_cors_preflight_allows_localhost_5174() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/chat/reply",
            headers={
                "Origin": "http://localhost:5174",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_stream_reply_returns_sse_events(sqlite_chat_db: None) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/reply/stream",
            json={
                "session_id": "session-test",
                "user_id": "user-test",
                "message": "我不想活了",
                "mode": "soothing",
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "event: token" in response.text
        assert "event: done" in response.text


def test_history_endpoint_returns_persisted_messages(sqlite_chat_db: None) -> None:
    with TestClient(app) as client:
        reply_response = client.post(
            "/api/v1/chat/reply",
            json={
                "session_id": "session-history",
                "user_id": "user-history",
                "message": "我不想活了",
                "mode": "soothing",
            },
        )

        assert reply_response.status_code == 200

        history_response = client.get(
            "/api/v1/chat/conversations",
            params={"user_id": "user-history"},
        )

        assert history_response.status_code == 200
        payload = history_response.json()
        assert payload["user_id"] == "user-history"
        assert len(payload["conversations"]) == 1

        conversation = payload["conversations"][0]
        assert conversation["id"] == "session-history"
        assert conversation["title"] == "我不想活了"
        assert conversation["preview"] == "我不想活了"
        assert [item["role"] for item in conversation["messages"]] == ["user", "assistant"]
        assert conversation["latest_trace"]["safety_level"] == "high"
