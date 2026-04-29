# -*- coding: utf-8 -*-
"""
Prompt 仓库：统一处理本地模板与 LangSmith Prompt 拉取。

目的：提供 PromptSpec 的统一获取能力，优先从 LangSmith 拉取，失败时回退本地模板。
结果：返回完整可用的 PromptSpec 实例，支持模板版本追踪。
"""

from __future__ import annotations

import logging
from typing import Any

from prompt.contracts import PromptSection, PromptSpec

from observability import TraceSanitizer, get_langsmith_service

logger = logging.getLogger(__name__)


class PromptRepository:
    """目的：封装持久化读写逻辑，隔离数据库访问细节和查询实现。
    结果：业务层可以通过统一仓储接口完成数据操作，降低存储实现耦合。
    """

    def __init__(self) -> None:
        """目的：初始化PromptRepository所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self._langsmith = get_langsmith_service()

    def resolve(
        self,
        *,
        prompt_identifier: str,
        fallback_spec: PromptSpec,
        variables: dict[str, Any],
    ) -> PromptSpec:
        """目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
        结果：返回标准化解析结果，便于后续链路复用和扩展。
        """
        prompt_obj = self._langsmith.pull_prompt(prompt_identifier)
        if prompt_obj is None:
            return fallback_spec

        rendered_messages = self._render_prompt_messages(prompt_obj, variables)
        if not rendered_messages:
            return fallback_spec

        system_prompt = rendered_messages.get("system") or fallback_spec.render_system_prompt()
        user_prompt = rendered_messages.get("user") or fallback_spec.render_user_prompt()
        return PromptSpec(
            name=fallback_spec.name,
            prompt_version=f"langsmith:{prompt_identifier}",
            output_schema_name=fallback_spec.output_schema_name,
            output_contract_version=fallback_spec.output_contract_version,
            system_sections=[PromptSection(name="langsmith_system", content=system_prompt)],
            user_sections=[PromptSection(name="langsmith_user", content=user_prompt)],
            fallback_policy=fallback_spec.fallback_policy,
        )

    def _render_prompt_messages(
        self,
        prompt_obj: Any,
        variables: dict[str, Any],
    ) -> dict[str, str] | None:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        try:
            rendered = prompt_obj.invoke(variables)
        except Exception as exc:
            logger.warning("LangSmith Prompt 渲染失败，回退本地模板: %s", exc)
            return None

        messages = getattr(rendered, "messages", None)
        if messages is None and isinstance(rendered, str):
            return {"system": rendered, "user": ""}
        if not messages:
            return None

        system_parts: list[str] = []
        user_parts: list[str] = []
        for message in messages:
            role = getattr(message, "type", "") or getattr(message, "role", "")
            content = self._extract_message_content(message)
            if role in {"system"}:
                system_parts.append(content)
            elif role in {"human", "user"}:
                user_parts.append(content)
        if not system_parts and not user_parts:
            return None
        return {
            "system": "\n\n".join(part for part in system_parts if part.strip()),
            "user": "\n\n".join(part for part in user_parts if part.strip()),
        }

    def _extract_message_content(self, message: Any) -> str:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        return TraceSanitizer.summarize_text(repr(content), limit=500)
