"""LLM Provider 基类：共享的 token 计数、消息构建和专用 structured 能力。"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import TYPE_CHECKING, Any, TypeVar

try:
    import tiktoken
except Exception:  # pragma: no cover - 依赖缺失时自动降级
    tiktoken = None  # type: ignore[assignment]

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from contracts.chat import ChatReplyModel, MemoryDecisionBatch
from llm.core.types import LlmMessage, McpCallInfo
from observability import format_pretty_json_log
from prompt import PromptSpec

if TYPE_CHECKING:
    from core.config import Settings

logger = logging.getLogger(__name__)
TStructured = TypeVar("TStructured", bound=BaseModel)


def _to_json_log(payload: dict[str, Any]) -> str:
    """目的：把 LLM 请求/响应转成可读 JSON 日志文本。"""
    return format_pretty_json_log(payload)


def _summarize_tools_for_log(tools: Any) -> dict[str, Any]:
    """目的：压缩工具 schema，只保留排查时最常用的信息。"""
    if not isinstance(tools, list):
        return {"count": 0, "names": []}

    names: list[str] = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if isinstance(function, dict) and function.get("name"):
            names.append(str(function["name"]))
    return {"count": len(tools), "names": names}


def _format_message_content_for_log(content: Any) -> dict[str, Any]:
    """目的：多行 prompt 按行展示，避免日志里出现一大串转义换行。"""
    if not isinstance(content, str):
        return {"content": content}
    if "\n" not in content:
        return {"content": content}
    return {"content_lines": content.splitlines()}


def _summarize_messages_for_log(messages: Any) -> list[dict[str, Any]]:
    """目的：保留消息顺序和角色，同时避免超长上下文刷屏。"""
    if not isinstance(messages, list):
        return []

    summaries: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            summaries.append({"index": index, "value": message})
            continue

        summary: dict[str, Any] = {
            "index": index,
            "role": message.get("role"),
        }
        summary.update(_format_message_content_for_log(message.get("content")))
        if message.get("tool_calls"):
            summary["tool_calls"] = message.get("tool_calls")
        if message.get("tool_call_id"):
            summary["tool_call_id"] = message.get("tool_call_id")
        summaries.append(summary)
    return summaries


def _summarize_llm_request_for_log(request: dict[str, Any]) -> dict[str, Any]:
    """目的：把原始 LLM 请求整理成更适合控制台阅读的结构。"""
    payload = dict(request)
    messages = payload.pop("messages", None)
    tools = payload.pop("tools", None)

    payload["message_count"] = len(messages) if isinstance(messages, list) else 0
    payload["messages"] = _summarize_messages_for_log(messages)
    if tools is not None:
        payload["tools"] = _summarize_tools_for_log(tools)
    return payload


def log_llm_request(
    logger_: logging.Logger,
    *,
    provider: str,
    stage: str,
    model: str,
    stream: bool,
    request: dict[str, Any],
) -> float:
    """目的：打印 LLM 请求并返回开始时间，用于响应耗时统计。
    结果：完成当前业务处理并返回约定结果。
    """
    logger_.info(
        "LLM 请求:\n%s",
        _to_json_log({
            "provider": provider,
            "stage": stage,
            "model": model,
            "stream": stream,
            "request": _summarize_llm_request_for_log(request),
        }),
    )
    return time.monotonic()


def log_llm_response(
    logger_: logging.Logger,
    *,
    provider: str,
    stage: str,
    model: str,
    stream: bool,
    request_started_at: float,
    response: dict[str, Any],
) -> None:
    """目的：打印 LLM 响应和耗时。
    结果：完成当前业务处理并返回约定结果。
    """
    logger_.info(
        "LLM 响应:\n%s",
        _to_json_log({
            "provider": provider,
            "stage": stage,
            "model": model,
            "stream": stream,
            "duration_ms": int((time.monotonic() - request_started_at) * 1000),
            "response": response,
        }),
    )

# 最大历史总 token 数（system + history + user_prompt），超出时优先从最旧消息开始截断
_MAX_TOTAL_TOKENS = 8192
# 最大保留历史消息条数（按消息对计，即 user + assistant 为一条对话轮次）
_MAX_HISTORY_MESSAGES = 6
# 函数调用循环最大轮次，防止无限循环
_MAX_FUNCTION_CALL_ROUNDS = 3

_OPENAI_MODEL_HINTS = ("gpt", "openai", "o1", "o3")
_HF_MODEL_REPO_MAP = {
    "deepseek": "deepseek-ai/DeepSeek-V3",
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
}


def _resolve_auto_tokenizer() -> Any | None:
    """目的：避免应用启动时就强依赖 Hugging Face tokenizer。
    结果：返回 AutoTokenizer 类型，缺失依赖时返回 None 并降级。
    """
    try:
        from transformers import AutoTokenizer as hf_auto_tokenizer
    except Exception:  # pragma: no cover - 依赖缺失时自动降级
        logger.warning("transformers 未安装，token 计数将无法使用 Hugging Face tokenizer。")
        return None
    return hf_auto_tokenizer


@lru_cache(maxsize=1)
def _get_tiktoken_encoder() -> Any | None:
    """目的：执行懒加载 tiktoken 编码器，避免导入失败影响主流程相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if tiktoken is None:
        logger.warning("tiktoken 未安装，token 计数将无法使用 tiktoken。")
        return None

    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # pragma: no cover - 外部依赖异常
        logger.warning("初始化 tiktoken 编码器失败，将尝试其他计数方式: %s", exc)
        return None


@lru_cache(maxsize=8)
def _load_hf_tokenizer(repo_id: str) -> Any | None:
    """目的：执行懒加载 Hugging Face tokenizer，并缓存实例避免重复下载相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    auto_tokenizer = _resolve_auto_tokenizer()
    if auto_tokenizer is None:
        return None

    try:
        return auto_tokenizer.from_pretrained(repo_id)
    except Exception as exc:  # pragma: no cover - 外部依赖异常
        logger.warning("加载 Hugging Face tokenizer 失败 [%s]，将尝试降级: %s", repo_id, exc)
        return None


class BaseLLmProvider(ABC):
    """目的：封装LLM Provider 抽象基类，定义统一的接口和共享逻辑相关的模型或能力实现。
    结果：上层可按统一 Provider 接口发起调用。
    """

    # 目的：保存 supports_structured_output 字段，用于 BaseLLmProvider 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 supports_structured_output 值。
    supports_structured_output = True

    def __init__(self, settings: "Settings") -> None:
        """目的：初始化BaseLLmProvider所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.settings = settings
        self._pending_tool_history: list[LlmMessage] | None = None

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> tuple[str, list[McpCallInfo]]:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        ...

    @abstractmethod
    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> AsyncIterator[tuple[str, list[McpCallInfo]]]:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        ...

    @abstractmethod
    def _get_model_name(self) -> str:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        ...

    @abstractmethod
    def _get_structured_client_options(self) -> dict[str, Any]:
        """目的：让不同 provider 提供各自的模型、密钥和 base_url。
        结果：返回可传给 ChatOpenAI 的配置字典。
        """
        ...

    def _resolve_hf_tokenizer_repo(self, model_name: str) -> str | None:
        """目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
        结果：返回标准化解析结果，便于后续链路复用和扩展。
        """
        configured_repo = str(getattr(self.settings, "hf_tokenizer_repo", "")).strip()
        if configured_repo:
            return configured_repo

        normalized_model = model_name.strip().lower()
        for prefix, repo_id in _HF_MODEL_REPO_MAP.items():
            if prefix in normalized_model:
                return repo_id
        return None

    def _resolve_tokenizer_backend(self) -> str:
        """目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
        结果：返回标准化解析结果，便于后续链路复用和扩展。
        """
        configured_backend = str(getattr(self.settings, "tokenizer_backend", "auto")).strip().lower()
        if configured_backend in {"tiktoken", "huggingface", "char_estimate"}:
            return configured_backend

        model_name = self._get_model_name().strip().lower()
        if any(hint in model_name for hint in _OPENAI_MODEL_HINTS):
            return "tiktoken"
        if any(prefix in model_name for prefix in _HF_MODEL_REPO_MAP):
            return "huggingface"
        if self._resolve_hf_tokenizer_repo(model_name):
            return "huggingface"

        logger.warning(
            "无法根据模型名自动判断 tokenizer 后端，已降级为字符估算: model=%s",
            self._get_model_name(),
        )
        return "char_estimate"

    def _count_tokens(self, text: str) -> int:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if not text:
            return 0

        backend = self._resolve_tokenizer_backend()
        model_name = self._get_model_name()

        if backend == "tiktoken":
            encoder = _get_tiktoken_encoder()
            if encoder is not None:
                return len(encoder.encode(text))
            logger.warning("tiktoken 不可用，已降级为字符估算: model=%s", model_name)
            return len(text) // 4 or 1

        if backend == "huggingface":
            repo_id = self._resolve_hf_tokenizer_repo(model_name)
            if repo_id:
                tokenizer = _load_hf_tokenizer(repo_id)
                if tokenizer is not None:
                    return len(tokenizer.encode(text, add_special_tokens=False))
                logger.warning(
                    "Hugging Face tokenizer 不可用，已降级为字符估算: model=%s, repo=%s",
                    model_name,
                    repo_id,
                )
            else:
                logger.warning(
                    "未找到 Hugging Face tokenizer repo，已降级为字符估算: model=%s",
                    model_name,
                )
            return len(text) // 4 or 1

        return len(text) // 4 or 1

    def _truncate_by_tokens(
        self,
        history: list[LlmMessage],
        system_prompt: str,
        user_prompt: str,
    ) -> list[dict[str, Any]]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        system_tokens = self._count_tokens(system_prompt)
        user_tokens = self._count_tokens(user_prompt)
        budget = _MAX_TOTAL_TOKENS - system_tokens - user_tokens - 50

        if budget <= 0 or not history:
            return []

        recent = history[-_MAX_HISTORY_MESSAGES * 2:]
        result: list[dict[str, Any]] = []
        accumulated = 0

        for msg in reversed(recent):
            content_raw = msg.get("content", "")
            content_str = str(content_raw) if content_raw else ""
            msg_tokens = self._count_tokens(content_str) + 4  # +4 估算 role/metadata 开销

            if accumulated + msg_tokens > budget:
                break

            result.append(msg)
            accumulated += msg_tokens

        result.reverse()
        return result

    def _build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[LlmMessage] | None = None,
    ) -> list[dict[str, Any]]:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if history:
            trimmed = self._truncate_by_tokens(history, system_prompt, user_prompt)
            messages.extend(trimmed)

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _reset_pending_tool_history(self) -> None:
        """目的：在 structured 终结完成后避免旧工具上下文污染下一轮对话。
        结果：pending tool history 被置空。
        """
        self._pending_tool_history = None

    def _set_pending_tool_history(self, history: list[LlmMessage]) -> None:
        """目的：在工具调用阶段结束后保留完整消息历史给 structured 终结使用。
        结果：pending tool history 持有一份独立历史副本。
        """
        self._pending_tool_history = list(history)

    def has_pending_tool_history(self) -> bool:
        """目的：提供工作流路由判断信号。
        结果：返回 True 表示需要继续执行工具终结回复。
        """
        return bool(self._pending_tool_history)

    async def finalize_chat_reply(
        self,
        prompt_spec: PromptSpec,
    ) -> tuple[ChatReplyModel, list[McpCallInfo]]:
        """目的：复用工具调用后的消息历史，调用 structured 输出生成 ChatReplyModel。
        结果：返回结构化回复和 MCP 调用记录，并清空 pending history。
        """
        if not self._pending_tool_history:
            raise RuntimeError("当前没有可用于 structured 终结的工具上下文。")

        pending_history = list(self._pending_tool_history)
        messages = self._build_messages(
            prompt_spec.render_system_prompt(),
            prompt_spec.render_user_prompt(),
            pending_history,
        )
        payload = await self._invoke_structured_output(messages, ChatReplyModel)
        self._reset_pending_tool_history()
        return payload, list(getattr(self, "_mcp_calls", []))

    async def decide_memory(
        self,
        prompt_spec: PromptSpec,
        *,
        history: list[LlmMessage] | None = None,
    ) -> tuple[MemoryDecisionBatch, list[McpCallInfo]]:
        """目的：使用 MemoryDecisionBatch schema 约束模型输出，判断是否保存长期记忆。
        结果：返回 MemoryDecisionBatch 和本次调用关联的 MCP 记录。
        """
        messages = self._build_messages(
            prompt_spec.render_system_prompt(),
            prompt_spec.render_user_prompt(),
            history,
        )
        payload = await self._invoke_structured_output(messages, MemoryDecisionBatch)
        return payload, list(getattr(self, "_mcp_calls", []))

    def _build_structured_chat_model(self) -> ChatOpenAI:
        """目的：集中创建 with_structured_output 阶段复用的 LangChain ChatOpenAI 实例。
        结果：返回按 provider 配置初始化的 ChatOpenAI。
        """
        return ChatOpenAI(**self._get_structured_client_options())

    async def _invoke_structured_output(
        self,
        messages: list[dict[str, Any]],
        output_schema: type[TStructured],
    ) -> TStructured:
        """目的：把消息列表发送给模型，并用 Pydantic schema 校验返回结构。
        结果：返回指定 output_schema 的实例。
        """
        model_name = self._get_model_name()
        started_at = log_llm_request(
            logger,
            provider=self.__class__.__name__,
            stage=f"structured.{output_schema.__name__}",
            model=model_name,
            stream=False,
            request={
                "messages": messages,
                "output_schema": output_schema.model_json_schema(),
            },
        )
        llm = self._build_structured_chat_model().with_structured_output(output_schema)
        payload = await llm.ainvoke(self._to_langchain_messages(messages))
        result = payload if isinstance(payload, output_schema) else output_schema.model_validate(payload)
        log_llm_response(
            logger,
            provider=self.__class__.__name__,
            stage=f"structured.{output_schema.__name__}",
            model=model_name,
            stream=False,
            request_started_at=started_at,
            response=result.model_dump(),
        )
        return result

    def _to_langchain_messages(self, messages: list[dict[str, Any]]) -> list[SystemMessage | HumanMessage | AIMessage]:
        """目的：兼容 system、user、assistant、tool 等内部角色格式。
        结果：返回 LangChain 可直接 ainvoke 的消息对象列表。
        """
        converted: list[SystemMessage | HumanMessage | AIMessage] = []
        for message in messages:
            role = str(message.get("role", "")).strip().lower()
            content = str(message.get("content") or "").strip()

            if role == "system":
                converted.append(SystemMessage(content=content))
                continue
            if role in {"user", "human"}:
                converted.append(HumanMessage(content=content))
                continue
            if role == "tool":
                tool_call_id = str(message.get("tool_call_id") or "").strip()
                label = f"工具结果[{tool_call_id}]" if tool_call_id else "工具结果"
                converted.append(HumanMessage(content=f"{label}：\n{content}"))
                continue

            if role == "assistant":
                tool_calls = message.get("tool_calls") or []
                if isinstance(tool_calls, list) and tool_calls:
                    tool_names: list[str] = []
                    for item in tool_calls:
                        function_payload = item.get("function") if isinstance(item, dict) else None
                        if isinstance(function_payload, dict):
                            name = str(function_payload.get("name") or "").strip()
                            if name:
                                tool_names.append(name)
                    if tool_names:
                        call_summary = f"工具调用：{', '.join(tool_names)}"
                        content = f"{content}\n\n{call_summary}".strip()
                converted.append(AIMessage(content=content))
                continue

            converted.append(HumanMessage(content=content))
        return converted
