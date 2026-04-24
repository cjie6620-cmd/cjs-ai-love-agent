import os

from core.config import Settings
from observability.langsmith_service import LangSmithService, TraceSanitizer


def test_trace_sanitizer_masks_identity_and_text() -> None:
    """验证 trace sanitizer masks identity and text。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    payload = {
        "user_id": "user-raw",
        "session_id": "session-raw",
        "message": "我最近真的非常非常难受，想一直跟你说话。" * 10,
        "nested": {
            "content": "这是需要被截断的长文本。" * 30,
        },
    }

    sanitized = TraceSanitizer.sanitize_payload(payload)

    assert sanitized["user_id"] != "user-raw"
    assert sanitized["session_id"] != "session-raw"
    assert "..." in sanitized["message"]
    assert sanitized["nested"]["content"].endswith("...")


def test_langsmith_service_configures_env(monkeypatch) -> None:
    """验证 langsmith service configures env。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    settings = Settings(
        langsmith_enabled=True,
        langsmith_tracing=True,
        langsmith_api_key="ls-key",
        langsmith_project="ai-love",
        langsmith_endpoint="https://api.smith.langchain.com",
        langsmith_privacy_mode=True,
    )
    service = LangSmithService(settings)

    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_INPUTS", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_OUTPUTS", raising=False)

    service.configure_environment()

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_HIDE_INPUTS"] == "true"
    assert os.environ["LANGSMITH_HIDE_OUTPUTS"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "ai-love"


def test_langsmith_service_can_expose_raw_inputs_outputs(monkeypatch) -> None:
    """验证本地调试模式下可以查看原始 trace 输入输出。"""
    settings = Settings(
        langsmith_enabled=True,
        langsmith_tracing=True,
        langsmith_api_key="ls-key",
        langsmith_project="ai-love",
        langsmith_endpoint="https://api.smith.langchain.com",
        langsmith_privacy_mode=False,
    )
    service = LangSmithService(settings)

    monkeypatch.delenv("LANGSMITH_HIDE_INPUTS", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_OUTPUTS", raising=False)

    payload = {
        "session_id": "session-raw",
        "message": "保留完整输入",
        "reply": "保留完整输出",
    }

    service.configure_environment()

    assert os.environ["LANGSMITH_HIDE_INPUTS"] == "false"
    assert os.environ["LANGSMITH_HIDE_OUTPUTS"] == "false"
    assert service.process_trace_inputs(payload) == payload
    assert service.process_trace_outputs(payload) == payload
