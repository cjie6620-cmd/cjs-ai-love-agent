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
- items[0].should_store=true
- items[0].memory_type=profile_summary
- items[0].memory_text=用户的名字是小明，偏好被称呼为小明
- items[0].canonical_key=profile:name
- items[0].importance_score=0.95
- items[0].confidence=0.98
- items[0].merge_strategy=replace
- items[0].reason_code=explicit_identity

示例2：不应该保存
输入片段：
- user_message：今天有点累，想随便聊聊
- assistant_reply：可以，我们慢慢聊，不用急着整理清楚
期望输出：
- items=[]

示例3：应该保存
输入片段：
- user_message：我每次和伴侣吵架都会先沉默，不太会马上表达
- assistant_reply：你在冲突里更像是先退回去保护自己
期望输出：
- items[0].should_store=true
- items[0].memory_type=profile_summary
- items[0].memory_text=用户在亲密关系冲突中倾向先沉默和自我保护
- items[0].canonical_key=profile:conflict_style
- items[0].importance_score=0.88
- items[0].confidence=0.92
- items[0].merge_strategy=append
- items[0].reason_code=stable_relationship_pattern

示例4：一轮多条都应该保存
输入片段：
- user_message：我叫小陈，不喜欢吃辣
- assistant_reply：记住啦，小陈，之后涉及吃的我会默认按不辣来理解
期望输出：
- items[0].canonical_key=profile:name
- items[0].memory_text=用户的名字是小陈
- items[1].canonical_key=preference:food_spicy
- items[1].memory_text=用户不喜欢吃辣"""


def build_memory_decision_prompt_spec(
    *,
    user_message: str,
    assistant_reply: str,
) -> PromptSpec:
    """目的：为后台 DeepSeek 结构化输出提供保守、可治理的长期记忆提取指令。
    结果：返回包含字段契约、禁止项和 few-shot 的 PromptSpec。
    """
    settings = get_settings()
    fallback_policy = (
        "MEMORY_SAVE_POLICY: conservative_extract_only. 信息不确定、价值不稳定或来源不是用户本人时，必须 should_store=false。\n"
        "只提取可长期复用的用户事实、偏好、稳定关系模式、长期目标和明确称呼。\n"
        "拒绝寒暄、临时情绪、一次性场景、普通问题、助手推测、助手编造内容和无关噪声。"
    )
    output_contract = (
        "请严格按照 MemoryExtractionResult / MemoryDecisionBatch schema 输出。\n"
        "顶层必须返回 items 数组；数组中的每一项都必须包含 should_store、memory_type、memory_text、canonical_key、importance_score、confidence、merge_strategy、reason_code。\n"
        "无可保存信息时返回 items=[]。不要输出 items 之外的额外解释。"
    )
    system_sections = [
        PromptSection(name="role", content="你是长期记忆治理分析器，只判断本轮对话是否值得进入用户长期记忆。"),
        PromptSection(name="task", content="从 user_message 和 assistant_reply 中抽取全部稳定且有长期价值的记忆项；如果没有稳定价值，返回空数组。"),
        PromptSection(name="store_policy", content="允许保存：\n- 用户明确身份、称呼、长期偏好\n- 稳定的亲密关系状态和沟通模式\n- 反复出现的情绪触发点或边界\n- 长期目标、重要经历、明确承诺"),
        PromptSection(name="reject_policy", content="必须拒绝：\n- 寒暄、感谢、闲聊\n- 今天/刚才/此刻的临时情绪\n- 一次性问题、一次性任务、短期安排\n- 助手自己的建议、猜测或编造内容\n- 与用户长期画像无关的噪声信息"),
        PromptSection(name="field_guide", content="每条记忆必须单独成项，不能把多个事实揉成一条。\ncanonical_key 需要使用稳定的类别键，例如 profile:name、preference:comfort_style、preference:food_spicy、relationship:partner_status。\nimportance_score 取值范围 0 到 1，低于 0.60 的内容通常不应保存。\nconfidence 取值范围 0 到 1，低于 0.70 的内容通常不应保存。\nmerge_strategy 只能是 insert、replace、append、skip；新事实优先 replace，补充稳定模式可用 append。"),
        PromptSection(name="examples", content=_MEMORY_FEW_SHOTS),
        PromptSection(name="output_contract", content=output_contract),
        PromptSection(name="fallback_policy", content=fallback_policy),
    ]
    user_sections = [
        PromptSection(name="context", content=f"user_message：{user_message.strip()}"),
        PromptSection(name="context", content=f"assistant_reply：{assistant_reply.strip()}"),
        PromptSection(name="instruction", content="MEMORY_SAVE_POLICY: conservative_extract_only; do_not_record_everything; ignore_irrelevant_context. 只输出 items 数组中的结构化字段，不要为了保存而保存。"),
    ]
    local_spec = PromptSpec(
        name="memory.extraction",
        prompt_version=_MEMORY_PROMPT_VERSION,
        output_schema_name="MemoryDecisionBatch",
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
