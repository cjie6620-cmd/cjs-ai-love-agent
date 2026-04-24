"""LLM Provider 基类：共享的 token 计数、消息构建和专用 structured 能力。"""

from __future__ import annotations

import logging
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

from contracts.chat import ChatReplyModel, MemoryDecision
from llm.core.types import LlmMessage, McpCallInfo
from prompt import PromptSpec

if TYPE_CHECKING:
    from core.config import Settings

logger = logging.getLogger(__name__)
TStructured = TypeVar("TStructured", bound=BaseModel)

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
    """按需加载 transformers.AutoTokenizer，避免应用启动时触发额外警告。"""
    try:
        from transformers import AutoTokenizer as hf_auto_tokenizer
    except Exception:  # pragma: no cover - 依赖缺失时自动降级
        logger.warning("transformers 未安装，token 计数将无法使用 Hugging Face tokenizer。")
        return None
    return hf_auto_tokenizer


@lru_cache(maxsize=1)
def _get_tiktoken_encoder() -> Any | None:
    """懒加载 tiktoken 编码器，避免导入失败影响主流程。
    
    目的：执行懒加载 tiktoken 编码器，避免导入失败影响主流程相关逻辑。
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
    """懒加载 Hugging Face tokenizer，并缓存实例避免重复下载。
    
    目的：执行懒加载 Hugging Face tokenizer，并缓存实例避免重复下载相关逻辑。
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
    """LLM Provider 抽象基类，定义统一的接口和共享逻辑。
    
    目的：封装LLM Provider 抽象基类，定义统一的接口和共享逻辑相关的模型或能力实现。
    结果：上层可按统一 Provider 接口发起调用。
    """

    supports_structured_output = True

    def __init__(self, settings: "Settings") -> None:
        """初始化 BaseLLmProvider。
        
        目的：初始化BaseLLmProvider所需的依赖、配置和初始状态。
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
        """非流式生成：直接返回完整响应。

        目的：根据当前上下文组装目标对象、消息或输出结构。
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
        """流式生成：逐步返回响应内容。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        ...

    @abstractmethod
    def _get_model_name(self) -> str:
        """获取当前 Provider 使用的模型名称。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        ...

    @abstractmethod
    def _get_structured_client_options(self) -> dict[str, Any]:
        """返回 with_structured_output 阶段使用的 ChatOpenAI 配置。"""
        ...

    def _resolve_hf_tokenizer_repo(self, model_name: str) -> str | None:
        """根据模型名解析对应的 HuggingFace tokenizer 仓库。

        目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
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
        """自动解析合适的 tokenizer 后端。

        目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
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
        """按当前模型选择合适 tokenizer 进行计数。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
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
        """按 token 数截断历史消息，超出上限时从最旧消息开始丢弃。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
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
        """构建完整的 messages 列表用于 LLM API 调用。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if history:
            trimmed = self._truncate_by_tokens(history, system_prompt, user_prompt)
            messages.extend(trimmed)

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _reset_pending_tool_history(self) -> None:
        """清空上一轮工具调用沉淀下来的上下文。"""
        self._pending_tool_history = None

    def _set_pending_tool_history(self, history: list[LlmMessage]) -> None:
        """保存工具调用结束后的上下文，供 structured 终结阶段复用。"""
        self._pending_tool_history = list(history)

    def has_pending_tool_history(self) -> bool:
        """返回当前是否存在待终结的工具调用上下文。"""
        return bool(self._pending_tool_history)

    async def finalize_chat_reply(
        self,
        prompt_spec: PromptSpec,
    ) -> tuple[ChatReplyModel, list[McpCallInfo]]:
        """基于最近一次 tool/MCP 上下文生成最终结构化回复。"""
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
    ) -> tuple[MemoryDecision, list[McpCallInfo]]:
        """执行长期记忆决策专用 structured 调用。"""
        messages = self._build_messages(
            prompt_spec.render_system_prompt(),
            prompt_spec.render_user_prompt(),
            history,
        )
        payload = await self._invoke_structured_output(messages, MemoryDecision)
        return payload, list(getattr(self, "_mcp_calls", []))

    def _build_structured_chat_model(self) -> ChatOpenAI:
        """构建 with_structured_output 阶段复用的 LangChain ChatOpenAI 实例。"""
        return ChatOpenAI(**self._get_structured_client_options())

    async def _invoke_structured_output(
        self,
        messages: list[dict[str, Any]],
        output_schema: type[TStructured],
    ) -> TStructured:
        """通过 LangChain with_structured_output 调用专用 schema。"""
        llm = self._build_structured_chat_model().with_structured_output(output_schema)
        payload = await llm.ainvoke(self._to_langchain_messages(messages))
        if isinstance(payload, output_schema):
            return payload
        return output_schema.model_validate(payload)

    def _to_langchain_messages(self, messages: list[dict[str, Any]]) -> list[SystemMessage | HumanMessage | AIMessage]:
        """把内部 message 结构转换成 LangChain message。"""
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
