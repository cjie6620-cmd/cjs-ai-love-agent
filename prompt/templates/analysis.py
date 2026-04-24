# -*- coding: utf-8 -*-
"""分析类 Prompt 模板。"""

from __future__ import annotations

from core.config import get_settings
from prompt.contracts import PromptSection, PromptSpec
from prompt.repository import PromptRepository

_MEMORY_PROMPT_VERSION = "memory.extraction.v2"
_MEMORY_OUTPUT_VERSION = "memory_extraction.v2"

_MEMORY_FEW_SHOTS = """示例1：应该保存
输入片段：
- user_message：我叫小明，以后你可以直接叫我小明
- assistant_reply：好呀小明，我记住这个称呼
期望输出：
- should_store=true
- memory_type=profile_summary
- memory_text=用户的名字是小明，偏好被称呼为小明
- canonical_key=profile:name
- importance_score=0.95
- confidence=0.98
- merge_strategy=replace
- reason_code=explicit_identity

示例2：不应该保存
输入片段：
- user_message：今天有点累，想随便聊聊
- assistant_reply：可以，我们慢慢聊，不用急着整理清楚
期望输出：
- should_store=false
- memory_type=none
- memory_text=
- canonical_key=
- importance_score=0.10
- confidence=0.90
- merge_strategy=skip
- reason_code=temporary_mood

示例3：应该保存
输入片段：
- user_message：我每次和伴侣吵架都会先沉默，不太会马上表达
- assistant_reply：你在冲突里更像是先退回去保护自己
期望输出：
- should_store=true
- memory_type=profile_summary
- memory_text=用户在亲密关系冲突中倾向先沉默和自我保护
- canonical_key=profile:conflict_style
- importance_score=0.88
- confidence=0.92
- merge_strategy=append
- reason_code=stable_relationship_pattern"""


def build_memory_decision_prompt_spec(
    *,
    user_message: str,
    assistant_reply: str,
) -> PromptSpec:
    """构建长期记忆结构化提取 PromptSpec。

    目的：为后台 DeepSeek 结构化输出提供保守、可治理的长期记忆提取指令。
    结果：返回包含字段契约、禁止项和 few-shot 的 PromptSpec。
    """
    settings = get_settings()
    fallback_policy = (
        "MEMORY_SAVE_POLICY: conservative_extract_only. 信息不确定、价值不稳定或来源不是用户本人时，必须 should_store=false。\n"
        "只提取可长期复用的用户事实、偏好、稳定关系模式、长期目标和明确称呼。\n"
        "拒绝寒暄、临时情绪、一次性场景、普通问题、助手推测、助手编造内容和无关噪声。"
    )
    output_contract = (
        "???? MemoryExtractionResult / MemoryDecision schema ???\n"
        "???should_store?memory_type?memory_text?canonical_key?importance_score?confidence?merge_strategy?reason_code?\n"
        "should_store=false ??memory_type=none?memory_text ? canonical_key ???merge_strategy=skip?"
    )
    system_sections = [
        PromptSection(name="role", content="你是长期记忆治理分析器，只判断本轮对话是否值得进入用户长期记忆。"),
        PromptSection(name="task", content="从 user_message 和 assistant_reply 中抽取一条最有价值的长期记忆；如果没有稳定价值，返回 should_store=false。"),
        PromptSection(name="store_policy", content="允许保存：\n- 用户明确身份、称呼、长期偏好\n- 稳定的亲密关系状态和沟通模式\n- 反复出现的情绪触发点或边界\n- 长期目标、重要经历、明确承诺"),
        PromptSection(name="reject_policy", content="必须拒绝：\n- 寒暄、感谢、闲聊\n- 今天/刚才/此刻的临时情绪\n- 一次性问题、一次性任务、短期安排\n- 助手自己的建议、猜测或编造内容\n- 与用户长期画像无关的噪声信息"),
        PromptSection(name="field_guide", content="canonical_key ?? ????:?? ????? profile:name?preference:comfort_style?relationship:partner_status?\nimportance_score ??????????? 0.60 ??????\nconfidence ????????????? 0.70 ??????\nmerge_strategy ?? insert?replace?append?skip?????????? replace????????? append?"),
        PromptSection(name="examples", content=_MEMORY_FEW_SHOTS),
        PromptSection(name="output_contract", content=output_contract),
        PromptSection(name="fallback_policy", content=fallback_policy),
    ]
    user_sections = [
        PromptSection(name="context", content=f"?????{user_message.strip()}"),
        PromptSection(name="context", content=f"?????{assistant_reply.strip()}"),
        PromptSection(name="instruction", content="MEMORY_SAVE_POLICY: conservative_extract_only; do_not_record_everything; ignore_irrelevant_context. 只输出结构化字段，不要为了保存而保存。"),
    ]
    local_spec = PromptSpec(
        name="memory.extraction",
        prompt_version=_MEMORY_PROMPT_VERSION,
        output_schema_name="MemoryExtractionResult",
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
