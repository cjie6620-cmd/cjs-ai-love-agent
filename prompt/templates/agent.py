# -*- coding: utf-8 -*-
"""Agent Prompt 模板：主聊天走纯文本，工具终结阶段走专用 structured 提示词。"""

from __future__ import annotations

from contracts.chat import ChatMode, EvidenceStatus, KnowledgeEvidence, MemoryHit
from core.config import get_settings
from prompt.contracts import PromptSection, PromptSpec
from prompt.repository import PromptRepository

_TEXT_PROMPT_VERSION = "chat.reply.v1"
_TEXT_OUTPUT_CONTRACT_VERSION = "chat_reply_text.v2"
_TOOL_FINAL_PROMPT_VERSION = "chat.reply.tool_final.v1"
_TOOL_FINAL_OUTPUT_CONTRACT_VERSION = "chat_reply_structured.v2"

_MODE_ROLE_MAP: dict[ChatMode, str] = {
    "companion": "你是温和、稳定、边界清晰的情感陪伴助手。",
    "advice": "你是擅长恋爱沟通拆解的顾问，回答要具体、可执行。",
    "style_clone": "你会参考用户偏好的表达风格，但不会突破安全边界。",
    "soothing": "你要先接住情绪，再给柔和、具体的安抚和下一步建议。",
}

_MODE_TONE_MAP: dict[ChatMode, str] = {
    "companion": "温暖、稳定、像成熟朋友",
    "advice": "直接、清楚、可执行",
    "style_clone": "贴近用户语气，但不过火",
    "soothing": "低刺激、柔和、能让人慢下来",
}

_CHAT_FEW_SHOTS = """示例1：
输入片段：
- 用户消息：分手三天了，我一直想给她发消息
- 证据状态：grounded
- 可参考知识：分手初期建议先降温，不要立即高频联系
理想回复：
我能理解你现在很想联系她，但分手刚发生时，先把节奏放慢会更稳。你今天先不要连续发消息，先把最想说的话记下来，等情绪降一点再判断要不要发。

示例2：
输入片段：
- 用户消息：我最近总觉得关系怪怪的，但也说不清
- 证据状态：no_grounding
- 可参考知识：无
理想回复：
如果你现在也说不清具体卡在哪，我们先别急着下结论。你可以先回想一下，最近让你最别扭的是联系频率、说话语气，还是相处时的距离感，我再陪你一起往下拆。"""

_TOOL_FINAL_FIELD_GUIDE = """请补齐以下字段语义：
- reply_text：最终发送给用户的自然中文回复
- intent：按当前模式填写 support / advice / style_clone / soothing
- tone：按当前模式填写 warm / direct / adaptive / gentle
- grounded_by_knowledge：这次结论是否明显依赖知识证据
- used_memory：这次回复是否吸收了长期记忆
- needs_followup：是否适合在下一轮继续追问
- fallback_reason：无可靠证据时可填 no_grounding 或 weak_grounding，否则留空
- safety_notes：只有确实需要提醒边界或安全时再填写
- used_evidence_ids：只填写本次实际依赖的 K 编号，没有就返回空数组"""


def _render_history(recent_messages: list[dict[str, str]] | None) -> str:
    """
    渲染最近对话历史。

    目的：将最近对话列表格式化为可读的提示词片段。
    结果：返回格式化的对话历史字符串，最多包含4条最近消息。
    """
    if not recent_messages:
        return "最近对话：无"

    snippets = []
    for item in recent_messages[-4:]:
        role = "用户" if item.get("role") == "user" else "助手"
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        snippets.append(f"- {role}：{content[:120]}")
    return "\n".join(snippets) or "最近对话：无"


def _render_memory_hits(memory_hits: list[MemoryHit]) -> str:
    """
    渲染长期记忆命中结果。

    目的：将长期记忆检索结果格式化为可读的提示词片段。
    结果：返回格式化的记忆命中字符串，最多包含3条记忆。
    """
    if not memory_hits:
        return "长期记忆：未命中"
    lines = []
    for index, hit in enumerate(memory_hits[:3], start=1):
        lines.append(
            f"- [{index}] score={hit['score']:.2f} content={str(hit['content']).strip()[:140]}"
        )
    return "\n".join(lines)


def _render_knowledge_hits(knowledge_hits: list[str]) -> str:
    """
    渲染知识检索命中结果。

    目的：将 RAG 知识检索结果格式化为可读的提示词片段。
    结果：返回格式化的知识命中字符串，最多包含4条知识片段。
    """
    if not knowledge_hits:
        return "知识证据：未命中"
    return "\n".join(
        f"- [CTX{index}] {item.strip()[:420]}"
        for index, item in enumerate(knowledge_hits[:4], start=1)
        if item.strip()
    ) or "知识证据：未命中"


def _render_knowledge_evidences(knowledge_evidences: list[KnowledgeEvidence]) -> str:
    """渲染结构化证据对象。"""
    if not knowledge_evidences:
        return "证据编号：无"
    lines: list[str] = []
    for item in knowledge_evidences[:6]:
        evidence = item if isinstance(item, KnowledgeEvidence) else KnowledgeEvidence.model_validate(item)
        heading = evidence.heading_path or evidence.title or "未命名片段"
        lines.append(
            f"- {evidence.evidence_id} | {heading} | source={evidence.source or 'unknown'} | snippet={evidence.snippet}"
        )
    return "\n".join(lines)


def _build_constraints(
    *,
    mode: ChatMode,
    safety_level: str,
    evidence_status: EvidenceStatus,
    llm_provider: str,
    structured_fields: bool = False,
) -> str:
    """
    构建约束条件文本。

    目的：根据对话模式、安全级别和证据状态生成相应的约束条件。
    结果：返回格式化的约束条件字符串。
    """
    constraints = [
        "输出必须是简洁、自然、像真人沟通的中文。",
        "不要逐条复述知识原文，要提炼成自然表达。",
        f"语气参考：{_MODE_TONE_MAP.get(mode, _MODE_TONE_MAP['companion'])}。",
        "不要做情感承诺，不要暗示自己可以替代现实关系或专业帮助。",
        "如果知识证据不足，不要假装查到了答案。",
        "不要暴露内部检索状态、证据来源或系统说明式开场白。",
    ]
    if structured_fields:
        constraints.extend(
            [
                "reply_text 要保持自然，不要写成字段说明。",
                "只要用了知识证据，就必须在 used_evidence_ids 中填写对应的 K 编号。",
                "如果没有可靠知识证据，used_evidence_ids 必须返回空数组。",
            ]
        )
    if safety_level == "medium":
        constraints.append("用户可能对 AI 有依赖倾向，回复要温暖但边界清晰。")
    if evidence_status == "no_grounding":
        constraints.append("当前没有稳定证据时，直接基于用户上下文给自然、保守、可执行的回复，不要解释内部检索状态。")
    elif evidence_status == "weak_grounding":
        constraints.append("可以参考命中内容，但要降低语气确定性，避免说得过满。")
    if llm_provider in {"xai_router", "openai_remote_mcp"}:
        constraints.append("只有确实需要外部实时信息时才允许触发工具。")
    return "\n".join(f"- {item}" for item in constraints)


def _build_user_sections(
    *,
    mode: ChatMode,
    safety_level: str,
    message: str,
    recent_messages: list[dict[str, str]] | None,
    memory_hits: list[MemoryHit],
    knowledge_hits: list[str],
    knowledge_evidences: list[KnowledgeEvidence],
    retrieval_query: str,
    evidence_status: EvidenceStatus,
) -> list[PromptSection]:
    """构建聊天主链路共用的上下文段。"""
    return [
        PromptSection(name="context", content=f"用户当前消息：{message.strip()}"),
        PromptSection(
            name="context",
            content=(
                f"当前模式：{mode}\n"
                f"安全级别：{safety_level}\n"
                f"检索查询：{retrieval_query or '无'}\n"
                f"知识证据状态：{evidence_status}"
            ),
        ),
        PromptSection(name="context", content=_render_history(recent_messages)),
        PromptSection(name="context", content=f"长期记忆命中：\n{_render_memory_hits(memory_hits)}"),
        PromptSection(name="evidence", content=f"父级上下文：\n{_render_knowledge_hits(knowledge_hits)}"),
        PromptSection(
            name="evidence",
            content=f"证据编号索引：\n{_render_knowledge_evidences(knowledge_evidences)}",
        ),
    ]


def build_chat_reply_prompt_spec(
    *,
    mode: ChatMode,
    safety_level: str,
    llm_provider: str,
    message: str,
    recent_messages: list[dict[str, str]] | None,
    memory_hits: list[MemoryHit],
    knowledge_hits: list[str],
    knowledge_evidences: list[KnowledgeEvidence],
    retrieval_query: str,
    evidence_status: EvidenceStatus,
) -> PromptSpec:
    """
    构建聊天主链路 PromptSpec。

    目的：整合对话上下文、长期记忆和知识证据，生成完整的聊天回复提示词。
    结果：返回可用于生成聊天回复的 PromptSpec 对象。
    """
    settings = get_settings()

    fallback_policy = (
        "grounded：优先基于知识证据给结论和下一步建议。\n"
        "weak_grounding：可以参考方向，但语气要更保守。\n"
        "no_grounding：直接根据用户当前信息给自然、保守、可执行的回复，必要时补一个简短追问。"
    )
    output_contract = (
        "本阶段只输出一段可直接发送给用户的纯文本回复。\n"
        "不要输出 JSON、字段名、标签、解释或系统说明。"
    )

    system_sections = [
        PromptSection(
            name="role",
            content=f"{_MODE_ROLE_MAP.get(mode, _MODE_ROLE_MAP['companion'])} 你服务于 AI Love Agent 的正式对话主链。",
        ),
        PromptSection(
            name="task",
            content="基于用户消息、最近对话、长期记忆和知识证据，生成一条可直接发送给用户的回复。",
        ),
        PromptSection(
            name="constraints",
            content=_build_constraints(
                mode=mode,
                safety_level=safety_level,
                evidence_status=evidence_status,
                llm_provider=llm_provider,
                structured_fields=False,
            ),
        ),
        PromptSection(name="examples", content=_CHAT_FEW_SHOTS),
        PromptSection(name="output_contract", content=output_contract),
        PromptSection(name="fallback_policy", content=fallback_policy),
    ]

    user_sections = _build_user_sections(
        mode=mode,
        safety_level=safety_level,
        message=message,
        recent_messages=recent_messages,
        memory_hits=memory_hits,
        knowledge_hits=knowledge_hits,
        knowledge_evidences=knowledge_evidences,
        retrieval_query=retrieval_query,
        evidence_status=evidence_status,
    )

    local_spec = PromptSpec(
        name="chat.reply",
        prompt_version=_TEXT_PROMPT_VERSION,
        output_schema_name="PlainTextReply",
        output_contract_version=_TEXT_OUTPUT_CONTRACT_VERSION,
        system_sections=system_sections,
        user_sections=user_sections,
        fallback_policy=fallback_policy,
    )
    prompt_repository = PromptRepository()
    return prompt_repository.resolve(
        prompt_identifier=settings.langsmith_prompt_chat_reply,
        fallback_spec=local_spec,
        variables={
            "mode": mode,
            "safety_level": safety_level,
            "llm_provider": llm_provider,
            "message": message.strip(),
            "recent_messages": _render_history(recent_messages),
            "memory_hits": _render_memory_hits(memory_hits),
            "knowledge_hits": _render_knowledge_hits(knowledge_hits),
            "knowledge_evidences": _render_knowledge_evidences(knowledge_evidences),
            "retrieval_query": retrieval_query or "无",
            "evidence_status": evidence_status,
            "fallback_policy": fallback_policy,
            "local_system_prompt": local_spec.render_system_prompt(),
            "local_user_prompt": local_spec.render_user_prompt(),
            "prompt_version": local_spec.prompt_version,
            "output_contract_version": local_spec.output_contract_version,
        },
    )


def build_tool_final_reply_prompt_spec(
    *,
    mode: ChatMode,
    safety_level: str,
    llm_provider: str,
    message: str,
    recent_messages: list[dict[str, str]] | None,
    memory_hits: list[MemoryHit],
    knowledge_hits: list[str],
    knowledge_evidences: list[KnowledgeEvidence],
    retrieval_query: str,
    evidence_status: EvidenceStatus,
) -> PromptSpec:
    """构建工具 / MCP 终结阶段使用的 structured 输出 PromptSpec。"""
    del llm_provider

    fallback_policy = (
        "如果工具结果不足以支撑明确结论，就保持保守表达。\n"
        "reply_text 仍然要自然、可直接发送，不要暴露内部工具链路。"
    )

    system_sections = [
        PromptSection(
            name="role",
            content=f"{_MODE_ROLE_MAP.get(mode, _MODE_ROLE_MAP['companion'])} 你正在执行工具调用后的最终回复整理阶段。",
        ),
        PromptSection(
            name="task",
            content="工具和 MCP 调用已经结束。你现在只负责基于既有上下文整理最终结构化回复，不要继续规划工具。",
        ),
        PromptSection(
            name="constraints",
            content=(
                _build_constraints(
                    mode=mode,
                    safety_level=safety_level,
                    evidence_status=evidence_status,
                    llm_provider="tool_final",
                    structured_fields=True,
                )
                + "\n- 本阶段禁止继续调用工具，只负责整理最终结果。"
            ),
        ),
        PromptSection(name="field_guide", content=_TOOL_FINAL_FIELD_GUIDE),
        PromptSection(name="fallback_policy", content=fallback_policy),
    ]

    user_sections = _build_user_sections(
        mode=mode,
        safety_level=safety_level,
        message=message,
        recent_messages=recent_messages,
        memory_hits=memory_hits,
        knowledge_hits=knowledge_hits,
        knowledge_evidences=knowledge_evidences,
        retrieval_query=retrieval_query,
        evidence_status=evidence_status,
    )
    user_sections.append(
        PromptSection(
            name="tool_phase",
            content="请结合上文已有的工具结果和当前上下文，输出最终结构化回复。",
        )
    )

    return PromptSpec(
        name="chat.reply.tool_final",
        prompt_version=_TOOL_FINAL_PROMPT_VERSION,
        output_schema_name="ChatReplyModel",
        output_contract_version=_TOOL_FINAL_OUTPUT_CONTRACT_VERSION,
        system_sections=system_sections,
        user_sections=user_sections,
        fallback_policy=fallback_policy,
    )
