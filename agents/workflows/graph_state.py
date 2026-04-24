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
    ConversationHistoryMessage,
    EvidenceStatus,
    KnowledgeEvidence,
    McpCallInfo,
    MemoryHit,
    QuestionAdvisorPayload,
)


def _merge_str(existing: str | None, new: str | None) -> str:
    """字符串归约：后者覆盖前者（空字符串不覆盖已有内容）。
    
    目的：执行字符串归约：后者覆盖前者（空字符串不覆盖已有内容）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if new is not None and new != "":
        return new
    return existing or ""


def _merge_chat_request(existing: ChatRequest | None, new: ChatRequest | None) -> ChatRequest:
    """ChatRequest 归约：返回新值（初始化后不变，取第一个非 None 值）。
    
    目的：执行ChatRequest 归约：返回新值（初始化后不变，取第一个非 None 值）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if new is not None:
        return new
    if existing is not None:
        return existing
    raise ValueError("CompanionState.request 至少需要一个非 None 值")


def _merge_recent_messages(
    existing: list[ConversationHistoryMessage] | None,
    new: list[ConversationHistoryMessage] | None,
) -> list[ConversationHistoryMessage] | None:
    """recent_messages 归约：只读字段，直接返回已有值（忽略并发写入）。
    
    目的：执行recent_messages 归约：只读字段，直接返回已有值（忽略并发写入）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return existing if existing is not None else new


def _merge_memory_hits(existing: list[MemoryHit], new: list[MemoryHit]) -> list[MemoryHit]:
    """记忆命中列表归约：按 chunk_id 去重，后者分数更高时替换。
    
    目的：执行记忆命中列表归约：按 chunk_id 去重，后者分数更高时替换相关逻辑。
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
    """列表归约：追加去重，保持顺序。
    
    目的：执行列表归约：追加去重，保持顺序相关逻辑。
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
    """布尔归约：优先使用新值。"""
    if new is not None:
        return new
    return bool(existing)


def _merge_evidences(
    existing: list[KnowledgeEvidence],
    new: list[KnowledgeEvidence],
) -> list[KnowledgeEvidence]:
    """按 evidence_id 去重，保留较新的详情。"""
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
    """MCP 调用列表归约：追加去重，基于 server_label + tool_name 唯一标识。
    
    目的：执行MCP 调用列表归约：追加去重，基于 server_label + tool_name 唯一标识相关逻辑。
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
    """流式 token 归约：按发生顺序顺延追加。
    
    目的：执行流式 token 归约：按发生顺序顺延追加相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return existing + new


class CompanionState(TypedDict):
    """LangGraph 对话状态：承载工作流各节点之间的数据流转。
    
    目的：封装LangGraph 对话状态：承载工作流各节点之间的数据流转相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    # 只读输入（初始化后不变，并发写入时取已有值）
    request: Annotated[ChatRequest, _merge_chat_request]
    recent_messages: Annotated[list[ConversationHistoryMessage] | None, _merge_recent_messages]

    # 归约字段
    safety_level: Annotated[str, _merge_str]
    advisor_draft: QuestionAdvisorPayload | None
    memory_hits: Annotated[list[MemoryHit], _merge_memory_hits]
    knowledge_hits: Annotated[list[str], _merge_list]
    knowledge_evidences: Annotated[list[KnowledgeEvidence], _merge_evidences]
    matched_topics: Annotated[list[str], _merge_list]
    retrieval_query: Annotated[str, _merge_str]
    evidence_status: Annotated[EvidenceStatus, _merge_str]
    answer_confidence: Annotated[AnswerConfidence, _merge_str]
    answer_confidence_reason: Annotated[str, _merge_str]
    rerank_applied: Annotated[bool, _merge_bool]
    prompt_version: Annotated[str, _merge_str]
    output_contract_version: Annotated[str, _merge_str]
    fallback_reason: Annotated[str, _merge_str]
    reply: Annotated[str, _merge_str]
    reply_structured: ChatReplyModel | None
    advisor: QuestionAdvisorPayload | None
    mode: ChatMode

    # 流式相关
    streaming_chunks: Annotated[list[str], _merge_streaming_chunks]

    # MCP 工具调用追踪
    mcp_calls: Annotated[list[McpCallInfo], _merge_mcp_calls]

    # 额外状态
    metadata: dict[str, object]


class CompanionUpdate(TypedDict, total=False):
    """节点局部更新：LangGraph 节点只返回变化字段。
    
    目的：封装节点局部更新：LangGraph 节点只返回变化字段相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    request: ChatRequest
    recent_messages: list[ConversationHistoryMessage] | None
    safety_level: str
    advisor_draft: QuestionAdvisorPayload | None
    memory_hits: list[MemoryHit]
    knowledge_hits: list[str]
    knowledge_evidences: list[KnowledgeEvidence]
    matched_topics: list[str]
    retrieval_query: str
    evidence_status: EvidenceStatus
    answer_confidence: AnswerConfidence
    answer_confidence_reason: str
    rerank_applied: bool
    prompt_version: str
    output_contract_version: str
    fallback_reason: str
    reply: str
    reply_structured: ChatReplyModel | None
    advisor: QuestionAdvisorPayload | None
    mode: ChatMode
    streaming_chunks: list[str]
    mcp_calls: list[McpCallInfo]
    metadata: dict[str, object]
