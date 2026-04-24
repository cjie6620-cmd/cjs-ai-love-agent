"""LangSmith 服务封装：统一管理 tracing、脱敏和 Prompt 拉取。"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import re
from contextlib import nullcontext
from functools import lru_cache
from typing import Any, Callable, cast

from pydantic import BaseModel

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 依赖可能在本地测试环境中缺失
    from langsmith import Client, traceable, tracing_context
    from langsmith.wrappers import wrap_openai
except Exception:  # pragma: no cover
    Client = None  # type: ignore[assignment,misc]
    wrap_openai = None  # type: ignore[assignment]
    traceable = None  # type: ignore[assignment]
    tracing_context = None  # type: ignore[assignment]


def _identity_decorator(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """_identity_decorator 方法。
    
    目的：执行_identity_decorator 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    def _wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return _wrap


class TraceSanitizer:
    """LangSmith 上报前的统一脱敏器。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    _TEXT_KEYS = {
        "message",
        "content",
        "reply",
        "reply_text",
        "user_prompt",
        "system_prompt",
        "user_message",
        "assistant_reply",
        "retrieval_query",
        "input_snapshot",
        "input_summary",
        "output_summary",
    }
    _IDENTITY_KEYS = {
        "user_id",
        "session_id",
        "thread_id",
        "conversation_id",
    }

    @classmethod
    def hash_identity(cls, value: str, *, prefix: str = "id") -> str:
        """生成稳定的脱敏标识。

        目的：统一处理输入值的边界情况、格式约束和清洗规则。
        结果：返回满足约束的结果，避免脏数据影响后续逻辑。
        """
        text = str(value or "").strip()
        if not text:
            return ""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{digest}"

    @classmethod
    def thread_id(cls, session_id: str) -> str:
        """执行 thread_id 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return cls.hash_identity(session_id, prefix="thread")

    @classmethod
    def summarize_text(cls, value: str | None, *, limit: int = 120) -> str:
        """生成简要摘要信息。

        目的：统一处理输入值的边界情况、格式约束和清洗规则。
        结果：返回满足约束的结果，避免脏数据影响后续逻辑。
        """
        if not value:
            return ""
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}..."

    @classmethod
    def sanitize_payload(cls, payload: Any, *, depth: int = 0) -> Any:
        """sanitize_payload 方法。
        
        目的：执行当前步骤对应的处理逻辑。
        结果：返回当前步骤的处理结果，供后续流程继续使用。
        """
        if depth > 4:
            return cls.summarize_text(repr(payload), limit=80)
        if payload is None or isinstance(payload, (bool, int, float)):
            return payload
        if isinstance(payload, str):
            return cls.summarize_text(payload)
        if isinstance(payload, BaseModel):
            return cls.sanitize_payload(payload.model_dump(), depth=depth + 1)
        if dataclasses.is_dataclass(payload) and not isinstance(payload, type):
            return cls.sanitize_payload(dataclasses.asdict(payload), depth=depth + 1)
        if isinstance(payload, dict):
            sanitized: dict[str, Any] = {}
            for raw_key, raw_value in payload.items():
                key = str(raw_key)
                lowered = key.lower()
                if lowered in cls._IDENTITY_KEYS:
                    sanitized[key] = cls.hash_identity(str(raw_value), prefix=lowered)
                elif lowered in cls._TEXT_KEYS:
                    sanitized[key] = cls.summarize_text(str(raw_value))
                else:
                    sanitized[key] = cls.sanitize_payload(raw_value, depth=depth + 1)
            return sanitized
        if isinstance(payload, (list, tuple, set)):
            values = list(payload)
            return {
                "count": len(values),
                "items": [cls.sanitize_payload(item, depth=depth + 1) for item in values[:5]],
            }
        return cls.summarize_text(repr(payload), limit=120)

    @classmethod
    def sanitize_trace_inputs(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        """sanitize_trace_inputs 方法。
        
        目的：执行当前步骤对应的处理逻辑。
        结果：返回当前步骤的处理结果，供后续流程继续使用。
        """
        return cls.sanitize_payload(inputs)

    @classmethod
    def sanitize_trace_outputs(cls, outputs: Any) -> Any:
        """sanitize_trace_outputs 方法。
        
        目的：执行当前步骤对应的处理逻辑。
        结果：返回当前步骤的处理结果，供后续流程继续使用。
        """
        return cls.sanitize_payload(outputs)

    @classmethod
    def request_metadata(
        cls,
        *,
        user_id: str,
        session_id: str,
        message: str,
        mode: str,
        risk_level: str,
        stream: bool,
        provider: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行 request_metadata 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        metadata = {
            "user_id_hash": cls.hash_identity(user_id, prefix="user"),
            "session_id_hash": cls.hash_identity(session_id, prefix="session"),
            "message_summary": cls.summarize_text(message, limit=96),
            "mode": mode,
            "risk_level": risk_level,
            "stream": stream,
            "provider": provider,
        }
        if extra:
            metadata.update(cls.sanitize_payload(extra))
        return metadata

    @classmethod
    def response_metadata(
        cls,
        *,
        prompt_version: str,
        output_contract_version: str,
        evidence_status: str,
        mcp_calls: list[Any],
        fallback_reason: str,
    ) -> dict[str, Any]:
        """执行 response_metadata 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return {
            "prompt_version": prompt_version,
            "output_contract_version": output_contract_version,
            "evidence_status": evidence_status,
            "fallback_reason": fallback_reason,
            "mcp_call_count": len(mcp_calls),
            "mcp_calls": cls.sanitize_payload(mcp_calls),
        }


class LangSmithService:
    """统一封装 LangSmith 配置、Prompt 拉取和客户端包装。

    目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化 LangSmithService。
        
        目的：初始化LangSmithService所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.settings = settings or get_settings()
        self._client: Any | None = None
        self._prompt_cache: dict[str, Any] = {}

    @property
    def package_available(self) -> bool:
        """执行 package_available 方法。

        目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return Client is not None

    @property
    def enabled(self) -> bool:
        """执行 enabled 方法。

        目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return bool(self.settings.langsmith_enabled)

    @property
    def tracing_enabled(self) -> bool:
        """执行 tracing_enabled 方法。

        目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return (
            self.enabled
            and bool(self.settings.langsmith_tracing)
            and bool(self.settings.langsmith_api_key.strip())
        )

    @property
    def privacy_mode(self) -> bool:
        """返回是否启用 LangSmith 隐私模式。"""
        return bool(self.settings.langsmith_privacy_mode)

    def configure_environment(self) -> None:
        """将 LangSmith 配置同步到环境变量，供 LangGraph / SDK 自动读取。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        mapping = {
            "LANGSMITH_TRACING": "true" if self.tracing_enabled else "false",
            "LANGSMITH_API_KEY": self.settings.langsmith_api_key.strip(),
            "LANGSMITH_PROJECT": self.settings.langsmith_project.strip(),
            "LANGSMITH_ENDPOINT": self.settings.langsmith_endpoint.strip(),
            "LANGSMITH_WORKSPACE_ID": self.settings.langsmith_workspace_id.strip(),
            "LANGSMITH_HIDE_INPUTS": "true" if self.privacy_mode else "false",
            "LANGSMITH_HIDE_OUTPUTS": "true" if self.privacy_mode else "false",
        }
        for key, value in mapping.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                os.environ.pop(key, None)

    def process_trace_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """按隐私模式决定是否对 trace 输入做脱敏。"""
        if not self.privacy_mode:
            return inputs
        return TraceSanitizer.sanitize_trace_inputs(inputs)

    def process_trace_outputs(self, outputs: Any) -> Any:
        """按隐私模式决定是否对 trace 输出做脱敏。"""
        if not self.privacy_mode:
            return outputs
        return TraceSanitizer.sanitize_trace_outputs(outputs)

    def get_client(self) -> Any | None:
        """获取目标资源或配置。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self.enabled or not self.package_available:
            return None
        if self._client is not None:
            return self._client
        if not self.settings.langsmith_api_key.strip():
            return None
        try:
            client_kwargs: dict[str, Any] = {
                "api_key": self.settings.langsmith_api_key.strip(),
            }
            if self.settings.langsmith_endpoint.strip():
                client_kwargs["api_url"] = self.settings.langsmith_endpoint.strip()
            if self.settings.langsmith_workspace_id.strip():
                client_kwargs["workspace_id"] = self.settings.langsmith_workspace_id.strip()
            self._client = Client(**client_kwargs)
            return self._client
        except Exception as exc:  # pragma: no cover - 外部服务异常
            logger.warning("LangSmith Client 初始化失败，已降级: %s", exc)
            return None

    def tracing_scope(self) -> Any:
        """执行 tracing_scope 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if tracing_context is None:
            return nullcontext()
        return tracing_context(enabled=self.tracing_enabled)

    def build_tags(
        self,
        *,
        mode: str,
        risk_level: str,
        provider: str,
        stream: bool,
    ) -> list[str]:
        """构建目标对象或结构。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        return [
            f"app_env:{self.settings.app_env}",
            f"mode:{mode}",
            f"risk_level:{risk_level}",
            f"provider:{provider}",
            "stream" if stream else "nonstream",
        ]

    def build_metadata(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        mode: str,
        risk_level: str,
        stream: bool,
        provider: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建目标对象或结构。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        return TraceSanitizer.request_metadata(
            user_id=user_id,
            session_id=session_id,
            message=message,
            mode=mode,
            risk_level=risk_level,
            stream=stream,
            provider=provider,
            extra=extra,
        )

    def wrap_openai_client(self, client: Any) -> Any:
        """执行 wrap_openai_client 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if client is None or wrap_openai is None or not self.tracing_enabled:
            return client
        if getattr(client, "_ai_love_langsmith_wrapped", False):
            return client
        try:
            wrapped = wrap_openai(client)
            setattr(wrapped, "_ai_love_langsmith_wrapped", True)
            return wrapped
        except Exception as exc:  # pragma: no cover - 外部 SDK 差异
            logger.warning("OpenAI 客户端接入 LangSmith 失败，已降级: %s", exc)
            return client

    def pull_prompt(self, identifier: str) -> Any | None:
        """执行 pull_prompt 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        normalized = identifier.strip()
        if not normalized:
            return None
        if normalized in self._prompt_cache:
            return self._prompt_cache[normalized]
        client = self.get_client()
        if client is None:
            return None
        try:
            prompt_obj = client.pull_prompt(normalized)
            self._prompt_cache[normalized] = prompt_obj
            return prompt_obj
        except Exception as exc:  # pragma: no cover - 远端依赖
            logger.warning("拉取 LangSmith Prompt 失败 [%s]，回退本地模板: %s", normalized, exc)
            return None

    def maybe_json(self, value: Any) -> str:
        """执行 maybe_json 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            return TraceSanitizer.summarize_text(repr(value), limit=300)


def _process_trace_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """traceable 装饰器输入处理入口。"""
    return get_langsmith_service().process_trace_inputs(inputs)


def _process_trace_outputs(outputs: Any) -> Any:
    """traceable 装饰器输出处理入口。"""
    return get_langsmith_service().process_trace_outputs(outputs)


def traceable_chain(
    name: str,
    *,
    run_type: str = "chain",
    reduce_fn: Callable[[list[Any]], Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """traceable_chain 方法。
    
    目的：执行traceable_chain 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if traceable is None:
        return _identity_decorator()
    traceable_fn = cast(Any, traceable)
    return cast(Callable[[Callable[..., Any]], Callable[..., Any]], traceable_fn(
        name=name,
        run_type=run_type,
        process_inputs=_process_trace_inputs,
        process_outputs=_process_trace_outputs,
        reduce_fn=reduce_fn,
    ))


def traceable_tool(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """traceable_tool 方法。
    
    目的：执行traceable_tool 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return traceable_chain(name, run_type="tool")


@lru_cache(maxsize=1)
def get_langsmith_service() -> LangSmithService:
    """get_langsmith_service 方法。
    
    目的：获取get_langsmith_service 。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    return LangSmithService()
