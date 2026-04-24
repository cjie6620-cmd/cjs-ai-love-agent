"""LangGraph 节点实现：安全检查、顾问构建、记忆召回、知识检索、回复生成、顾问完成、输出过滤。

目的：将统一对话工作流拆分为独立节点函数。
结果：使 LangGraph 状态图能够按需编排执行路径。每个节点接收状态、执行业务逻辑并返回更新后的状态。
"""

from __future__ import annotations

import logging

from observability import traceable_chain
from prompt import PromptSpec
from prompt.templates import (
    build_chat_reply_prompt_spec,
    build_tool_final_reply_prompt_spec,
)

from contracts.chat import (
    AnswerConfidence,
    ChatMode,
    ChatReplyModel,
    EvidenceStatus,
    KnowledgeEvidence,
    QuestionAdvisorPayload,
)
from ..question_advisor import QuestionAdvisor, QuestionAdvisorDraft
from .graph_state import CompanionState, CompanionUpdate
from .runtime import get_workflow_runtime

logger = logging.getLogger(__name__)


def _convert_to_llm_history(
    recent_messages: list | None,
) -> list[dict[str, str]] | None:
    """将 ConversationHistoryMessage 列表转换为 LLM 历史消息格式。
    
    目的：执行将 ConversationHistoryMessage 列表转换为 LLM 历史消息格式相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if not recent_messages:
        return None
    return [{"role": msg.role, "content": msg.content} for msg in recent_messages]


def build_safe_fallback_reply(safety_level: str) -> str | None:
    """根据安全级别返回固定兜底回复。

    目的：让非流式和流式路径共用同一份 high 风险兜底文案。
    结果：避免两个入口各写一套逻辑，后续修改时出现行为不一致。
    """
    if safety_level != "high":
        return None
    return (
        "我能感受到你现在情绪很重，我们先把节奏放慢一点。"
        "如果你愿意，我可以先陪你把发生的事理清楚。"
    )


def build_reply_generation_context(
    state: CompanionState,
) -> tuple[PromptSpec, list[dict[str, str]] | None]:
    """构造回复生成所需的 system prompt、user prompt 和历史消息。

    目的：把提示词组装逻辑抽成公共函数。
    结果：保证非流式 `generate_reply` 和流式 `langgraph_adapter.stream()` 使用完全一致的上下文。
    """
    request = state["request"]
    runtime = get_workflow_runtime()
    history = _convert_to_llm_history(state["recent_messages"])
    prompt_spec = build_chat_reply_prompt_spec(
        mode=state["mode"],
        safety_level=state["safety_level"],
        llm_provider=runtime.settings.llm_provider,
        message=request.message,
        recent_messages=history,
        memory_hits=state["memory_hits"],
        knowledge_hits=state["knowledge_hits"],
        knowledge_evidences=state["knowledge_evidences"],
        retrieval_query=state["retrieval_query"],
        evidence_status=state["evidence_status"],
    )
    return prompt_spec, history


def _best_evidence_score(evidence: KnowledgeEvidence) -> float:
    """返回单条证据的最佳可用分数。"""
    for value in (
        evidence.rerank_score,
        evidence.fusion_score,
        evidence.dense_score,
        evidence.bm25_score,
    ):
        if value is not None:
            return float(value)
    return 0.0


def _infer_evidence_status(results: list[KnowledgeEvidence]) -> EvidenceStatus:
    """根据检索结果判断当前证据强度。
    
    目的：执行根据检索结果判断当前证据强度相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if not results:
        return "no_grounding"
    top_score = max(_best_evidence_score(item) for item in results)
    parent_count = len({item.parent_id for item in results if item.parent_id})
    if top_score >= 0.55 and parent_count >= 2:
        return "grounded"
    return "weak_grounding"


def _infer_answer_confidence(
    evidences: list[KnowledgeEvidence],
    *,
    evidence_status: EvidenceStatus,
    rerank_applied: bool,
) -> tuple[AnswerConfidence, str]:
    """基于规则推断回答置信度。"""
    if not evidences:
        return "low", "当前没有检索到稳定证据，回答仅能作为低置信参考。"

    parent_count = len({item.parent_id for item in evidences if item.parent_id})
    if rerank_applied and evidence_status == "grounded" and parent_count >= 2:
        return "high", "已命中多条父级证据，且重排成功，回答可信度较高。"
    if rerank_applied:
        return "medium", "已有相关证据并完成重排，但证据覆盖度仍然有限。"
    return "low", "当前未完成重排或证据较弱，回答可信度较低。"


def _build_knowledge_evidences(parent_contexts: list, candidates: list) -> list[KnowledgeEvidence]:
    """把最终候选 child 转成 trace 证据对象。"""
    evidence_list: list[KnowledgeEvidence] = []
    parent_title_map = {context.parent_id: context.title for context in parent_contexts}
    for index, item in enumerate(candidates, start=1):
        evidence_id = f"K{index}"
        snippet = item.content.strip()
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        evidence_list.append(
            KnowledgeEvidence(
                evidence_id=evidence_id,
                chunk_id=item.chunk_id,
                parent_id=item.parent_id,
                title=parent_title_map.get(item.parent_id, item.title),
                source=item.source,
                heading_path=item.heading_path,
                snippet=snippet,
                dense_score=item.dense_score,
                bm25_score=item.bm25_score,
                fusion_score=item.fusion_score,
                rerank_score=item.rerank_score,
                rank=index,
                locator=item.locator,
            )
        )
    return evidence_list


def _build_chat_reply_fallback(
    *,
    reply_text: str,
    mode: ChatMode,
    evidence_status: EvidenceStatus,
    used_memory: bool,
    fallback_reason: str,
    safety_level: str,
) -> ChatReplyModel:
    """构建兜底场景下使用的 ChatReplyModel。"""
    return build_local_chat_reply(
        reply_text=reply_text,
        mode=mode,
        evidence_status=evidence_status,
        used_memory=used_memory,
        safety_level=safety_level,
        knowledge_evidences=[],
        fallback_reason=fallback_reason,
    )


def _resolve_chat_intent(mode: ChatMode) -> str:
    """按业务模式映射 reply intent。"""
    intent_map: dict[ChatMode, str] = {
        "companion": "support",
        "advice": "advice",
        "style_clone": "style_clone",
        "soothing": "soothing",
    }
    return intent_map.get(mode, "support")


def _resolve_chat_tone(mode: ChatMode) -> str:
    """按业务模式映射回复语气。"""
    tone_map = {
        "companion": "warm",
        "advice": "direct",
        "style_clone": "adaptive",
        "soothing": "gentle",
    }
    return tone_map.get(mode, "warm")


def _default_fallback_reason(evidence_status: EvidenceStatus) -> str:
    """根据证据强弱推断默认 fallback_reason。"""
    if evidence_status == "no_grounding":
        return "no_grounding"
    if evidence_status == "weak_grounding":
        return "weak_grounding"
    return ""


def _resolve_used_evidence_ids(
    evidence_status: EvidenceStatus,
    knowledge_evidences: list[KnowledgeEvidence],
) -> list[str]:
    """本地规则下选出可回填到 ChatReplyModel 的证据编号。"""
    if evidence_status != "grounded":
        return []
    return [
        item.evidence_id
        for item in knowledge_evidences[:2]
        if item.evidence_id
    ]


def build_local_chat_reply(
    *,
    reply_text: str,
    mode: ChatMode,
    evidence_status: EvidenceStatus,
    used_memory: bool,
    safety_level: str,
    knowledge_evidences: list[KnowledgeEvidence],
    fallback_reason: str | None = None,
) -> ChatReplyModel:
    """普通聊天分支用本地确定性逻辑组装 ChatReplyModel。"""
    safety_notes: list[str] = []
    if safety_level in {"medium", "high"}:
        safety_notes.append("保持边界清晰，避免替代真实关系。")
    return ChatReplyModel(
        reply_text=reply_text,
        intent=_resolve_chat_intent(mode),
        tone=_resolve_chat_tone(mode),
        grounded_by_knowledge=evidence_status == "grounded",
        used_memory=used_memory,
        needs_followup=evidence_status != "grounded",
        fallback_reason=(
            fallback_reason
            if fallback_reason is not None
            else _default_fallback_reason(evidence_status)
        ),
        safety_notes=safety_notes,
        used_evidence_ids=_resolve_used_evidence_ids(evidence_status, knowledge_evidences),
    )


def _filter_meaningful_mcp_calls(calls: list) -> list:
    """过滤掉 skipped / none 这类无效工具调用记录。"""
    return [
        call
        for call in calls
        if getattr(call, "status", "") != "skipped" and getattr(call, "tool_name", "") != "none"
    ]


def build_tool_final_prompt_context(state: CompanionState) -> PromptSpec:
    """构建工具 / MCP 终结阶段使用的 structured prompt。"""
    request = state["request"]
    runtime = get_workflow_runtime()
    history = _convert_to_llm_history(state["recent_messages"])
    return build_tool_final_reply_prompt_spec(
        mode=state["mode"],
        safety_level=state["safety_level"],
        llm_provider=runtime.settings.llm_provider,
        message=request.message,
        recent_messages=history,
        memory_hits=state["memory_hits"],
        knowledge_hits=state["knowledge_hits"],
        knowledge_evidences=state["knowledge_evidences"],
        retrieval_query=state["retrieval_query"],
        evidence_status=state["evidence_status"],
    )


# ============================ 节点实现 ============================ #


@traceable_chain("workflow.safety_check")
async def safety_check(state: CompanionState) -> CompanionUpdate:
    """安全检查节点：inspect_input 安全级别判断 + high/medium 事件审计日志。

    目的：识别用户输入中的高风险（自杀/暴力）和中风险（过度依赖/越界）内容。
    结果：high 级别触发硬拦截；medium 级别注入边界意识提示。
    """
    guard = get_workflow_runtime().safety_guard
    request = state["request"]
    metadata = state.get("metadata", {})
    prefetched = metadata.get("risk_level")
    safety_level = (
        str(prefetched)
        if isinstance(prefetched, str) and prefetched.strip()
        else guard.inspect_input(request.message)
    )

    # high/medium 安全事件写入审计日志（fire-and-forget）
    if safety_level in ("high", "medium"):
        action = "block" if safety_level == "high" else "warn"
        try:
            guard.log_safety_event(
                user_id=request.user_id,
                risk_level=safety_level,
                input_snapshot=request.message,
                action=action,
                session_id=request.session_id,
            )
        except Exception as exc:
            logger.warning("安全事件审计日志写入失败（不影响主流程）: %s", exc)

    return {"safety_level": safety_level}


@traceable_chain("workflow.build_advisor_draft")
def build_advisor_draft(state: CompanionState) -> CompanionUpdate:
    """顾问草稿构建节点：基于规则生成 issue_summary 和 retrieval_query。

    目的：根据用户当前消息和历史消息生成问题摘要和检索查询。
    结果：用于后续的记忆召回和知识检索。
    """
    advisor = QuestionAdvisor()
    request = state["request"]
    draft = advisor.build_draft(
        message=request.message,
        mode=state["mode"],
        recent_messages=state["recent_messages"],
    )
    return {
        "retrieval_query": draft.retrieval_query,
        "advisor_draft": QuestionAdvisorPayload(
            issue_summary=draft.issue_summary,
            retrieval_query=draft.retrieval_query,
            matched_topics=[],
            suggested_questions=[],
        ),
    }


@traceable_chain("workflow.recall_memory")
async def recall_memory(state: CompanionState) -> CompanionUpdate:
    """长期记忆召回节点：基于 retrieval_query 从向量库检索语义相关的用户记忆。

    目的：将用户长期记忆中与当前话题相关的内容召回。
    结果：作为 LLM 回复的上下文补充。
    """
    request = state["request"]
    retrieval_query = state["retrieval_query"]
    if not retrieval_query:
        return {"memory_hits": []}

    try:
        manager = get_workflow_runtime().memory_manager
        hits = await manager.recall(request.user_id, query=retrieval_query, top_k=3)
        return {"memory_hits": hits}
    except Exception as exc:
        logger.warning("记忆召回异常，降级为空结果: %s", exc)
        return {"memory_hits": []}


@traceable_chain("workflow.search_knowledge")
async def search_knowledge(state: CompanionState) -> CompanionUpdate:
    """知识检索节点：RRF 双路融合检索，从知识库中查找相关内容。

    目的：使用 QuestionAdvisor 改写的检索 query 和原始用户消息作为双路查询。
    结果：通过 Reciprocal Rank Fusion 融合排序，提高检索覆盖率。
    """
    request = state["request"]
    retrieval_query = state["retrieval_query"]
    if not retrieval_query:
        return {
            "knowledge_hits": [],
            "knowledge_evidences": [],
            "matched_topics": [],
            "answer_confidence": "low",
            "answer_confidence_reason": "未生成有效检索 query，回答可信度较低。",
            "rerank_applied": False,
        }

    try:
        retriever = get_workflow_runtime().knowledge_retriever
        advisor = QuestionAdvisor()
        top_k = 5 if state["mode"] in {"advice", "soothing", "style_clone"} else 4
        fusion_queries = [retrieval_query, request.message]
        retrieval = await retriever.search_with_context(fusion_queries, top_k=top_k)
        hits = [context.content for context in retrieval.parent_contexts]
        evidences = _build_knowledge_evidences(
            retrieval.parent_contexts,
            retrieval.candidates,
        )
        evidence_status = _infer_evidence_status(evidences)
        answer_confidence, answer_confidence_reason = _infer_answer_confidence(
            evidences,
            evidence_status=evidence_status,
            rerank_applied=retrieval.rerank_applied,
        )

        matched = advisor.extract_matched_topics(
            [
                str(
                    context.heading_path
                    or context.title
                    or context.content.splitlines()[0]
                )
                for context in retrieval.parent_contexts
                if context.content.strip()
            ]
        )
        return {
            "knowledge_hits": hits,
            "knowledge_evidences": evidences,
            "matched_topics": matched,
            "evidence_status": evidence_status,
            "answer_confidence": answer_confidence,
            "answer_confidence_reason": answer_confidence_reason,
            "rerank_applied": retrieval.rerank_applied,
        }
    except Exception as exc:
        logger.warning("知识检索异常，降级为空结果: %s", exc)
        return {
            "knowledge_hits": [],
            "knowledge_evidences": [],
            "matched_topics": [],
            "evidence_status": "no_grounding",
            "answer_confidence": "low",
            "answer_confidence_reason": "知识检索异常，回答可信度较低。",
            "rerank_applied": False,
        }


@traceable_chain("workflow.generate_reply")
async def generate_reply(state: CompanionState) -> CompanionUpdate:
    """LLM 回复生成节点：组装 system prompt + user prompt，调用 LLM 生成回复。

    目的：整合安全级别、记忆命中、知识命中和对话历史，构建结构化提示词并调用 LLM。
    结果：生成最终回复。high 安全级别触发短路口，返回安全兜底回复。

    当 llm_provider 为 openai_remote_mcp 时：
    - 系统提示词注入 MCP 工具使用策略
    - 捕获 MCP 调用追踪信息，写入状态以供后续节点和 SSE done 事件使用
    """
    safety_level = state["safety_level"]

    # high 级别：返回安全兜底回复（后续 output_guard 会做清洗）
    safe_reply = build_safe_fallback_reply(safety_level)
    if safe_reply is not None:
        structured = _build_chat_reply_fallback(
            reply_text=safe_reply,
            mode=state["mode"],
            evidence_status=state["evidence_status"],
            used_memory=bool(state["memory_hits"]),
            fallback_reason="safety_short_circuit",
            safety_level=safety_level,
        )
        return {
            "reply": safe_reply,
            "reply_structured": structured,
            "fallback_reason": structured.fallback_reason,
            "prompt_version": "chat.reply.v1",
            "output_contract_version": "chat_reply_text.v2",
        }

    prompt_spec, history = build_reply_generation_context(state)

    try:
        client = get_workflow_runtime().build_llm_client()
        raw_reply = await client.generate(
            prompt_spec.render_system_prompt(),
            prompt_spec.render_user_prompt(),
            history=history,
        )
        reply = raw_reply.strip() or "抱歉，我刚才没有组织好这句话，我们再试一次。"

        mcp_calls = client.get_mcp_calls()
        meaningful_calls = _filter_meaningful_mcp_calls(mcp_calls)

        if meaningful_calls and client.has_pending_tool_history():
            final_prompt_spec = build_tool_final_prompt_context(state)
            structured = await client.finalize_chat_reply(final_prompt_spec)
            if not structured.reply_text.strip():
                structured = structured.model_copy(
                    update={"reply_text": reply, "fallback_reason": structured.fallback_reason or "empty_reply"}
                )
            reply = structured.reply_text
            prompt_version = final_prompt_spec.prompt_version
            output_contract_version = final_prompt_spec.output_contract_version
        else:
            structured = build_local_chat_reply(
                reply_text=reply,
                mode=state["mode"],
                evidence_status=state["evidence_status"],
                used_memory=bool(state["memory_hits"]),
                safety_level=safety_level,
                knowledge_evidences=state["knowledge_evidences"],
                fallback_reason="empty_reply" if not raw_reply.strip() else None,
            )
            prompt_version = prompt_spec.prompt_version
            output_contract_version = prompt_spec.output_contract_version

        # 调试日志：记录 generate_reply 节点的实际返回值
        logger.info(
            "[generate_reply] 回复内容长度=%d, mcp_calls数量=%d, reply前50字符='%s'",
            len(reply),
            len(mcp_calls),
            reply[:50] if reply else "",
        )

        update: CompanionUpdate = {
            "reply": reply,
            "reply_structured": structured,
            "prompt_version": prompt_version,
            "output_contract_version": output_contract_version,
            "fallback_reason": structured.fallback_reason,
        }
        if meaningful_calls:
            update["mcp_calls"] = meaningful_calls
        return update
    except Exception as exc:
        logger.warning("LLM 生成异常，返回兜底回复: %s", exc)
        structured = _build_chat_reply_fallback(
            reply_text="抱歉，生成回复时遇到了问题，请稍后再试。",
            mode=state["mode"],
            evidence_status=state["evidence_status"],
            used_memory=bool(state["memory_hits"]),
            fallback_reason="llm_error",
            safety_level=safety_level,
        )
        return {
            "reply": structured.reply_text,
            "reply_structured": structured,
            "prompt_version": "chat.reply.v1",
            "output_contract_version": "chat_reply_text.v2",
            "fallback_reason": structured.fallback_reason,
        }


@traceable_chain("workflow.finalize_advisor")
def finalize_advisor(state: CompanionState) -> CompanionUpdate:
    """顾问完成节点：基于检索结果和 AI 回复生成建议问题列表。

    目的：根据问题场景、对话模式和匹配主题生成追问建议。
    结果：生成 4 条相关的追问建议，引导用户深入对话。
    """
    advisor = QuestionAdvisor()
    draft = state["advisor_draft"]

    # 兜底：advisor_draft 未构建时用空 draft
    if draft is None:
        draft = QuestionAdvisorPayload(
            issue_summary=state.get("retrieval_query", ""),
            retrieval_query=state.get("retrieval_query", ""),
            matched_topics=[],
            suggested_questions=[],
        )

    # QuestionAdvisor.finalize 接收 QuestionAdvisorDraft dataclass
    draft_dc = QuestionAdvisorDraft(
        issue_summary=draft.issue_summary,
        retrieval_query=draft.retrieval_query,
    )

    finalized = advisor.finalize(
        draft=draft_dc,
        mode=state["mode"],
        matched_topics=state["matched_topics"],
        reply=state["reply"],
    )
    return {"advisor": finalized}


@traceable_chain("workflow.output_guard")
def output_guard(state: CompanionState) -> CompanionUpdate:
    """输出过滤节点：inspect_output 清洗 AI 回复中的越界表达。

    目的：对 LLM 生成的回复执行安全增强：
    - 所有级别：替换越界表达（如"我也爱你" → 安全替代）
    - high 级别：附加紧急援助资源信息

    结果：返回清洗后的 reply 内容。
    """
    guard = get_workflow_runtime().safety_guard
    cleaned = guard.inspect_output(state["reply"], state["safety_level"])
    update: CompanionUpdate = {"reply": cleaned}
    structured = state.get("reply_structured")
    if structured is not None and structured.reply_text != cleaned:
        update["reply_structured"] = structured.model_copy(update={"reply_text": cleaned})
    return update
