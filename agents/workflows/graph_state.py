"""LangGraph 状态定义：TypedDict + Annotated Reducer 模式。

目的：定义对话状态图的共享状态结构，使用 Annotated 绑定归约函数。
结果：确保多轮对话中状态字段的正确合并语义。
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from contracts.chat import (
    AnswerConfidence,
    ChatMode,
    ChatReplyModel,
    ChatRequest,
    ConversationContext,
    EvidenceStatus,
    KnowledgeEvidence,
    McpCallInfo,
    MemoryHit,
    QuestionAdvisorPayload,
)


def _merge_str(existing: str | None, new: str | None) -> str:
    """目的：执行字符串归约：后者覆盖前者（空字符串不覆盖已有内容）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if new is not None and new != "":
        return new
    return existing or ""


def _merge_chat_request(existing: ChatRequest | None, new: ChatRequest | None) -> ChatRequest:
    """目的：执行ChatRequest 归约：返回新值（初始化后不变，取第一个非 None 值）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if new is not None:
        return new
    if existing is not None:
        return existing
    raise ValueError("CompanionState.request 至少需要一个非 None 值")


def _merge_conversation_context(
    existing: ConversationContext | None,
    new: ConversationContext | None,
) -> ConversationContext | None:
    """目的：执行recent_messages 归约：只读字段，直接返回已有值（忽略并发写入）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return existing if existing is not None else new


def _merge_memory_hits(existing: list[MemoryHit], new: list[MemoryHit]) -> list[MemoryHit]:
    """目的：执行记忆命中列表归约：按 chunk_id 去重，后者分数更高时替换相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    merged: list[MemoryHit] = []
    seen_index: dict[str, int] = {}

    for hit in [*existing, *new]:
        chunk_id = hit["chunk_id"]
        if not chunk_id:
            merged.append(hit)
            continue

        index = seen_index.get(chunk_id)
        if index is None:
            seen_index[chunk_id] = len(merged)
            merged.append(hit)
            continue

        if hit["score"] > merged[index]["score"]:
            merged[index] = hit
    return merged


def _merge_list(existing: list[str], new: list[str]) -> list[str]:
    """目的：执行列表归约：追加去重，保持顺序相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    seen: set[str] = set(existing)
    result = list(existing)
    for item in new:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_bool(existing: bool | None, new: bool | None) -> bool:
    """目的：在 LangGraph 状态合并时优先采用节点产生的新布尔值。
    结果：返回新值或旧值转换后的布尔结果。
    """
    if new is not None:
        return new
    return bool(existing)


def _merge_evidences(
    existing: list[KnowledgeEvidence],
    new: list[KnowledgeEvidence],
) -> list[KnowledgeEvidence]:
    """目的：在并行节点写入证据时去重，并保留后到节点提供的更新详情。
    结果：返回顺序稳定且 evidence_id 不重复的证据列表。
    """
    merged: dict[str, KnowledgeEvidence] = {
        item.evidence_id: item
        for item in existing
        if item.evidence_id
    }
    ordered = [item for item in existing if item.evidence_id]
    for item in new:
        if not item.evidence_id:
            continue
        if item.evidence_id not in merged:
            ordered.append(item)
        merged[item.evidence_id] = item
    return [merged[item.evidence_id] for item in ordered]


def _merge_mcp_calls(
    existing: list[McpCallInfo], new: list[McpCallInfo]
) -> list[McpCallInfo]:
    """目的：执行MCP 调用列表归约：追加去重，基于 server_label + tool_name 唯一标识相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    merged: list[McpCallInfo] = list(existing)
    seen_keys: set[tuple[str, str]] = set()
    for call in existing:
        seen_keys.add((call.server_label, call.tool_name))
    for call in new:
        key = (call.server_label, call.tool_name)
        if key not in seen_keys:
            merged.append(call)
            seen_keys.add(key)
        else:
            # 替换已存在的同名调用（保留最新记录）
            for i, existing_call in enumerate(merged):
                if (existing_call.server_label, existing_call.tool_name) == key:
                    merged[i] = call
                    break
    return merged


def _merge_streaming_chunks(existing: list[str], new: list[str]) -> list[str]:
    """目的：执行流式 token 归约：按发生顺序顺延追加相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return existing + new


class CompanionState(TypedDict):
    """目的：封装LangGraph 对话状态：承载工作流各节点之间的数据流转相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    # 只读输入（初始化后不变，并发写入时取已有值）
    # 当前请求体，承载用户消息、会话标识和业务模式。
    # 目的：保存 request 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 request 值。
    request: Annotated[ChatRequest, _merge_chat_request]
    # 会话上下文快照，包含最近消息、画像等供节点读取的上下文信息。
    # 目的：保存 conversation_context 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_context 值。
    conversation_context: Annotated[ConversationContext | None, _merge_conversation_context]

    # 归约字段
    # 安全分级结果，供后续节点决定是否走兜底回复。
    # 目的：保存 safety_level 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_level 值。
    safety_level: Annotated[str, _merge_str]
    # 问题推荐的草稿结果，后续可在 finalize 阶段补全为最终建议。
    # 目的：保存 advisor_draft 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 advisor_draft 值。
    advisor_draft: QuestionAdvisorPayload | None
    # 长期/会话记忆召回命中列表。
    # 目的：保存 memory_hits 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_hits 值。
    memory_hits: Annotated[list[MemoryHit], _merge_memory_hits]
    # 知识检索命中的标题或摘要文本列表，主要用于提示词拼装。
    # 目的：保存 knowledge_hits 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_hits 值。
    knowledge_hits: Annotated[list[str], _merge_list]
    # 结构化知识证据列表，用于 trace、引用和置信度判断。
    # 目的：保存 knowledge_evidences 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_evidences 值。
    knowledge_evidences: Annotated[list[KnowledgeEvidence], _merge_evidences]
    # 当前问题命中的主题标签，供顾问建议和检索分析使用。
    # 目的：保存 matched_topics 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 matched_topics 值。
    matched_topics: Annotated[list[str], _merge_list]
    # 实际发给知识检索层的查询语句。
    # 目的：保存 retrieval_query 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 retrieval_query 值。
    retrieval_query: Annotated[str, _merge_str]
    # 当前回复的证据落地状态，如 grounded / weak_grounding / no_grounding。
    # 目的：保存 evidence_status 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 evidence_status 值。
    evidence_status: Annotated[EvidenceStatus, _merge_str]
    # 对最终回答可信度的分级判断。
    # 目的：保存 answer_confidence 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 answer_confidence 值。
    answer_confidence: Annotated[AnswerConfidence, _merge_str]
    # 对置信度判断的自然语言解释，便于 trace 和调试。
    # 目的：保存 answer_confidence_reason 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 answer_confidence_reason 值。
    answer_confidence_reason: Annotated[str, _merge_str]
    # 本次检索是否执行了 rerank。
    # 目的：保存 rerank_applied 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_applied 值。
    rerank_applied: Annotated[bool, _merge_bool]
    # 本次回复生成所使用的 prompt 模板版本。
    # 目的：保存 prompt_version 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 prompt_version 值。
    prompt_version: Annotated[str, _merge_str]
    # 输出结构契约版本，便于前后端和观测链路对齐。
    # 目的：保存 output_contract_version 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_contract_version 值。
    output_contract_version: Annotated[str, _merge_str]
    # 兜底原因，例如安全短路、无证据、空回复等。
    # 目的：保存 fallback_reason 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fallback_reason 值。
    fallback_reason: Annotated[str, _merge_str]
    # 最终展示给用户的文本回复。
    # 目的：保存 reply 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reply 值。
    reply: Annotated[str, _merge_str]
    # 结构化回复对象，承载意图、语气、证据引用等字段。
    # 目的：保存 reply_structured 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reply_structured 值。
    reply_structured: ChatReplyModel | None
    # 最终返回给前端的追问建议或顾问推荐。
    # 目的：保存 advisor 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 advisor 值。
    advisor: QuestionAdvisorPayload | None
    # 当前对话模式，如陪伴、建议、风格复刻等。
    # 目的：保存 mode 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: ChatMode

    # 流式相关
    # 流式生成过程中累计的 token/chunk 列表。
    # 目的：保存 streaming_chunks 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 streaming_chunks 值。
    streaming_chunks: Annotated[list[str], _merge_streaming_chunks]

    # MCP 工具调用追踪
    # 本轮回复实际触发过的 MCP 工具调用记录。
    # 目的：保存 mcp_calls 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_calls 值。
    mcp_calls: Annotated[list[McpCallInfo], _merge_mcp_calls]

    # 额外状态
    # 运行时附加元数据，如风险等级、链路追踪附加信息等。
    # 目的：保存 metadata 字段，用于 CompanionState 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata 值。
    metadata: dict[str, object]


class CompanionUpdate(TypedDict, total=False):
    """目的：封装节点局部更新：LangGraph 节点只返回变化字段相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    # 当前请求体，通常只在初始化或特殊补写场景下回传。
    # 目的：保存 request 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 request 值。
    request: ChatRequest
    # 会话上下文增量更新，节点可按需补写最近消息或画像信息。
    # 目的：保存 conversation_context 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_context 值。
    conversation_context: ConversationContext | None
    # 安全分级结果。
    # 目的：保存 safety_level 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_level 值。
    safety_level: str
    # 问题推荐草稿。
    # 目的：保存 advisor_draft 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 advisor_draft 值。
    advisor_draft: QuestionAdvisorPayload | None
    # 记忆召回结果。
    # 目的：保存 memory_hits 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_hits 值。
    memory_hits: list[MemoryHit]
    # 知识命中文本结果。
    # 目的：保存 knowledge_hits 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_hits 值。
    knowledge_hits: list[str]
    # 结构化知识证据。
    # 目的：保存 knowledge_evidences 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_evidences 值。
    knowledge_evidences: list[KnowledgeEvidence]
    # 命中的主题标签。
    # 目的：保存 matched_topics 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 matched_topics 值。
    matched_topics: list[str]
    # 检索查询语句。
    # 目的：保存 retrieval_query 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 retrieval_query 值。
    retrieval_query: str
    # 证据落地状态。
    # 目的：保存 evidence_status 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 evidence_status 值。
    evidence_status: EvidenceStatus
    # 回答置信度等级。
    # 目的：保存 answer_confidence 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 answer_confidence 值。
    answer_confidence: AnswerConfidence
    # 置信度原因说明。
    # 目的：保存 answer_confidence_reason 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 answer_confidence_reason 值。
    answer_confidence_reason: str
    # 是否执行重排。
    # 目的：保存 rerank_applied 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_applied 值。
    rerank_applied: bool
    # prompt 模板版本。
    # 目的：保存 prompt_version 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 prompt_version 值。
    prompt_version: str
    # 输出结构契约版本。
    # 目的：保存 output_contract_version 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_contract_version 值。
    output_contract_version: str
    # 兜底原因。
    # 目的：保存 fallback_reason 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fallback_reason 值。
    fallback_reason: str
    # 最终回复文本。
    # 目的：保存 reply 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reply 值。
    reply: str
    # 结构化回复结果。
    # 目的：保存 reply_structured 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reply_structured 值。
    reply_structured: ChatReplyModel | None
    # 最终顾问建议。
    # 目的：保存 advisor 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 advisor 值。
    advisor: QuestionAdvisorPayload | None
    # 当前对话模式。
    # 目的：保存 mode 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: ChatMode
    # 流式输出增量片段。
    # 目的：保存 streaming_chunks 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 streaming_chunks 值。
    streaming_chunks: list[str]
    # MCP 工具调用记录。
    # 目的：保存 mcp_calls 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_calls 值。
    mcp_calls: list[McpCallInfo]
    # 额外元数据。
    # 目的：保存 metadata 字段，用于 CompanionUpdate 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata 值。
    metadata: dict[str, object]
