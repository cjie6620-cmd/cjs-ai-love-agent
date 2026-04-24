# -*- coding: utf-8 -*-
"""分析类 Prompt 模板：面向长期记忆决策等专用 structured 任务。"""

from __future__ import annotations

from core.config import get_settings
from prompt.contracts import PromptSection, PromptSpec
from prompt.repository import PromptRepository

_MEMORY_PROMPT_VERSION = "memory.decision.v1"
_MEMORY_OUTPUT_VERSION = "memory_decision.v1"

_MEMORY_FEW_SHOTS = """示例1：
输入片段：
- user_message：我每次一吵架就会先沉默，不太会马上表达
- assistant_reply：你在冲突里更容易先收回自己
期望判断：
- should_store=true
- memory_type=profile_summary
- memory_text=用户在冲突中容易先沉默和退回自我保护
- confidence=0.92
- reason_code=stable_profile

示例2：
输入片段：
- user_message：今天有点烦，想随便聊聊
- assistant_reply：可以，我们慢慢聊
期望判断：
- should_store=false
- memory_type=none
- memory_text=
- confidence=0.08
- reason_code=no_long_term_value"""


def build_memory_decision_prompt_spec(
    *,
    user_message: str,
    assistant_reply: str,
) -> PromptSpec:
    """
    构建长期记忆决策 PromptSpec。

    目的：基于用户消息和助手回复，判断对话是否值得写入长期记忆。
    结果：返回用于判断记忆价值的 PromptSpec 对象。
    """
    settings = get_settings()

    fallback_policy = (
        "如果不确定这段对话是否值得长期保存，默认 should_store=false。\n"
        "不要为了凑字段而编造记忆。"
    )
    output_contract = (
        "请围绕 should_store、memory_type、memory_text、confidence、reason_code 做判断。\n"
        "如果没有长期价值，就明确给出 should_store=false。"
    )

    system_sections = [
        PromptSection(
            name="role",
            content="你是长期记忆决策助手，负责判断本轮对话是否值得写入用户长期记忆。",
        ),
        PromptSection(
            name="task",
            content=(
                "从用户消息和助手回复里提炼真正值得长期保存的信息。"
                "只关注重要事件、稳定偏好、性格画像、关系关键角色。"
            ),
        ),
        PromptSection(
            name="constraints",
            content=(
                "- 空泛情绪、一次性寒暄、重复信息不要存。\n"
                "- memory_text 必须是一句简洁、稳定、可检索的话。\n"
                "- should_store=false 时，memory_type 必须为 none，memory_text 置空字符串。"
            ),
        ),
        PromptSection(name="examples", content=_MEMORY_FEW_SHOTS),
        PromptSection(name="output_contract", content=output_contract),
        PromptSection(name="fallback_policy", content=fallback_policy),
    ]

    user_sections = [
        PromptSection(name="context", content=f"用户消息：{user_message.strip()}"),
        PromptSection(name="context", content=f"助手回复：{assistant_reply.strip()}"),
        PromptSection(
            name="evidence",
            content=(
                "重点判断：\n"
                "- 是否出现长期稳定的信息\n"
                "- 是否出现重要关系事件\n"
                "- 是否出现后续对话值得复用的人设/偏好"
            ),
        ),
    ]

    local_spec = PromptSpec(
        name="memory.decision",
        prompt_version=_MEMORY_PROMPT_VERSION,
        output_schema_name="MemoryDecision",
        output_contract_version=_MEMORY_OUTPUT_VERSION,
        system_sections=system_sections,
        user_sections=user_sections,
        fallback_policy=fallback_policy,
    )
    prompt_repository = PromptRepository()
    return prompt_repository.resolve(
        prompt_identifier=settings.langsmith_prompt_memory_decision,
        fallback_spec=local_spec,
        variables={
            "user_message": user_message.strip(),
            "assistant_reply": assistant_reply.strip(),
            "fallback_policy": fallback_policy,
            "local_system_prompt": local_spec.render_system_prompt(),
            "local_user_prompt": local_spec.render_user_prompt(),
            "prompt_version": local_spec.prompt_version,
            "output_contract_version": local_spec.output_contract_version,
        },
    )
