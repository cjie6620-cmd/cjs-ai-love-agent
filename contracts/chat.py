"""聊天与工作流相关的共享契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, Field, field_validator

ChatMode = Literal["companion", "advice", "style_clone", "soothing"]
EvidenceStatus = Literal["grounded", "weak_grounding", "no_grounding"]
MemoryType = Literal["event", "preference", "profile_summary", "none"]
AnswerConfidence = Literal["high", "medium", "low"]
CacheLevel = Literal["none", "l1_exact", "l2_semantic", "l3_api"]
MemoryMergeStrategy = Literal["insert", "replace", "append", "skip"]
StreamTaskStatus = Literal["running", "cancelling", "cancelled", "completed", "failed"]
CancelStreamStatus = Literal["cancelling", "cancelled", "completed", "not_found"]
ReplyStatus = Literal["completed", "interrupted"]


class MemoryHit(TypedDict):
    """目的：描述长期记忆命中项的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 content 字段，用于 MemoryHit 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: str
    # 目的：保存 score 字段，用于 MemoryHit 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 score 值。
    score: float
    # 目的：保存 chunk_id 字段，用于 MemoryHit 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunk_id 值。
    chunk_id: str


class ChatRequest(BaseModel):
    """目的：描述聊天请求的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 session_id 字段，用于 ChatRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 session_id 值。
    session_id: str = Field(..., description="会话唯一标识")
    # 目的：保存 user_id 字段，用于 ChatRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: str = Field(default="", description="用户唯一标识，由后端认证或访客 Cookie 注入")
    # 目的：保存 message 字段，用于 ChatRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 message 值。
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入消息")
    # 目的：保存 mode 字段，用于 ChatRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: ChatMode = Field(default="companion", description="当前对话模式")


class McpCallInfo(BaseModel):
    """目的：描述MCP 工具调用追踪信息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 server_label 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 server_label 值。
    server_label: str = Field(description="MCP 服务器标签")
    # 目的：保存 tool_name 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tool_name 值。
    tool_name: str = Field(description="被调用的工具名称")
    # 目的：保存 status 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Literal["success", "error", "skipped"] = Field(description="调用状态")
    # 目的：保存 duration_ms 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 duration_ms 值。
    duration_ms: int = Field(description="调用耗时（毫秒）")
    # 目的：保存 input_summary 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 input_summary 值。
    input_summary: str = Field(default="", description="输入摘要")
    # 目的：保存 output_summary 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_summary 值。
    output_summary: str = Field(default="", description="输出摘要")
    # 目的：保存 error_message 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 error_message 值。
    error_message: str = Field(default="", description="错误信息")


class KnowledgeEvidence(BaseModel):
    """目的：描述一次知识库检索命中的可引用证据及其排序分数。
    结果：回复生成、链路追踪和前端展示可以共享同一份证据结构。
    """

    # 目的：保存 evidence_id 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 evidence_id 值。
    evidence_id: str = Field(default="", description="证据编号，供模型和 trace 对齐")
    # 目的：保存 chunk_id 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunk_id 值。
    chunk_id: str = Field(default="", description="命中的子块 ID")
    # 目的：保存 parent_id 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 parent_id 值。
    parent_id: str = Field(default="", description="父块 ID")
    # 目的：保存 title 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str = Field(default="", description="文档标题")
    # 目的：保存 source 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str = Field(default="", description="来源")
    # 目的：保存 heading_path 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_path 值。
    heading_path: str = Field(default="", description="章节路径")
    # 目的：保存 snippet 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 snippet 值。
    snippet: str = Field(default="", description="证据摘要")
    # 目的：保存 dense_score 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 dense_score 值。
    dense_score: float | None = Field(default=None, description="向量召回得分")
    # 目的：保存 bm25_score 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 bm25_score 值。
    bm25_score: float | None = Field(default=None, description="BM25 召回得分")
    # 目的：保存 fusion_score 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fusion_score 值。
    fusion_score: float | None = Field(default=None, description="融合得分")
    # 目的：保存 rerank_score 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_score 值。
    rerank_score: float | None = Field(default=None, description="重排得分")
    # 目的：保存 rank 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rank 值。
    rank: int = Field(default=0, description="最终排序位置")
    # 目的：保存 locator 字段，用于 KnowledgeEvidence 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 locator 值。
    locator: str = Field(default="", description="定位信息，如文件名/章节")


class ChatReplyModel(BaseModel):
    """目的：描述结构化聊天回复的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 reply_text 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reply_text 值。
    reply_text: str = Field(default="", description="最终发送给用户的文本")
    # 目的：保存 intent 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 intent 值。
    intent: str = Field(default="support", description="回复意图")
    # 目的：保存 tone 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tone 值。
    tone: str = Field(default="warm", description="回复语气")
    # 目的：保存 grounded_by_knowledge 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 grounded_by_knowledge 值。
    grounded_by_knowledge: bool = Field(default=False, description="是否基于知识证据")
    # 目的：保存 used_memory 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 used_memory 值。
    used_memory: bool = Field(default=False, description="是否吸收长期记忆")
    # 目的：保存 needs_followup 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 needs_followup 值。
    needs_followup: bool = Field(default=False, description="是否建议下一轮追问")
    # 目的：保存 fallback_reason 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fallback_reason 值。
    fallback_reason: str = Field(default="", description="兜底原因")
    # 目的：保存 safety_notes 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_notes 值。
    safety_notes: list[str] = Field(default_factory=list, description="安全备注")
    # 目的：保存 used_evidence_ids 字段，用于 ChatReplyModel 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 used_evidence_ids 值。
    used_evidence_ids: list[str] = Field(
        default_factory=list,
        description="本次回答实际使用到的证据编号",
    )

    @field_validator("reply_text", mode="before")
    @classmethod
    def normalize_reply_text(cls, value: object) -> str:
        """目的：标准化 reply_text 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return str(value or "").strip()


class MemoryDecision(BaseModel):
    """目的：约束后台大模型对单轮对话的长期记忆分析输出，统一存储价值、治理键和合并策略。
    结果：Celery 记忆任务可以基于该结构完成跳过、新增、替换或合并写入。
    """

    # 目的：保存 should_store 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 should_store 值。
    should_store: bool = Field(default=False, description="是否写入长期记忆")
    # 目的：保存 memory_type 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_type 值。
    memory_type: MemoryType = Field(default="none", description="记忆类型")
    # 目的：保存 memory_text 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_text 值。
    memory_text: str = Field(default="", description="归一化后的记忆文本")
    # 目的：保存 canonical_key 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 canonical_key 值。
    canonical_key: str = Field(default="", description="同类记忆的稳定治理键")
    # 目的：保存 importance_score 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 importance_score 值。
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="长期价值重要性评分")
    # 目的：保存 confidence 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 confidence 值。
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    # 目的：保存 merge_strategy 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 merge_strategy 值。
    merge_strategy: MemoryMergeStrategy = Field(default="skip", description="同类记忆命中后的合并策略")
    # 目的：保存 reason_code 字段，用于 MemoryDecision 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reason_code 值。
    reason_code: str = Field(default="no_value", description="原因编码")

    @field_validator("memory_text", mode="before")
    @classmethod
    def normalize_memory_text(cls, value: object) -> str:
        """目的：清理模型输出中的空值和首尾空白，避免脏文本进入治理链路。
        结果：返回可继续校验和持久化的记忆文本。
        """
        return str(value or "").strip()

    @field_validator("canonical_key", mode="before")
    @classmethod
    def normalize_canonical_key(cls, value: object) -> str:
        """目的：收敛模型输出的治理键格式，保证同类记忆可以稳定去重。
        结果：返回小写、去空白的 canonical_key。
        """
        return str(value or "").strip().lower()

    @field_validator("reason_code", mode="before")
    @classmethod
    def normalize_reason_code(cls, value: object) -> str:
        """目的：清理模型输出中的空值和首尾空白，保证跳过或保存原因可观测。
        结果：返回稳定的 reason_code。
        """
        return str(value or "no_value").strip() or "no_value"

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, value: MemoryType, info) -> MemoryType:
        """目的：根据 should_store 约束 memory_type，避免跳过结果携带可写入类型。
        结果：返回与写入决策一致的记忆类型。
        """
        should_store = bool(info.data.get("should_store", False))
        if should_store:
            return "event" if value == "none" else value
        return "none"

    @field_validator("memory_text")
    @classmethod
    def validate_memory_text(cls, value: str, info) -> str:
        """目的：限制可写入文本长度，并在跳过时清空文本。
        结果：返回符合长期记忆存储约束的文本。
        """
        should_store = bool(info.data.get("should_store", False))
        if should_store:
            return value[:180]
        return ""

    @field_validator("canonical_key")
    @classmethod
    def validate_canonical_key(cls, value: str, info) -> str:
        """目的：保证可写入记忆具备去重合并所需的稳定键，跳过结果不保留治理键。
        结果：返回可用于查询的 canonical_key。
        """
        should_store = bool(info.data.get("should_store", False))
        if not should_store:
            return ""
        return value[:96] or "memory:general"

    @field_validator("merge_strategy")
    @classmethod
    def validate_merge_strategy(cls, value: MemoryMergeStrategy, info) -> MemoryMergeStrategy:
        """目的：保证跳过结果不会触发写入策略，并保留模型返回的合并意图。
        结果：返回与 should_store 一致的合并策略。
        """
        should_store = bool(info.data.get("should_store", False))
        if not should_store:
            return "skip"
        return value


class MemoryDecisionBatch(BaseModel):
    """目的：长期记忆批量提取结果。
    结果：提供 MemoryDecisionBatch 的结构化能力，供业务流程复用。
    """

    # 目的：保存 items 字段，用于 MemoryDecisionBatch 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 items 值。
    items: list[MemoryDecision] = Field(default_factory=list, description="本轮对话中可保存的长期记忆列表")

    @field_validator("items", mode="before")
    @classmethod
    def normalize_items(cls, value: object) -> list[object]:
        """目的：标准化批量记忆列表输入。
        结果：返回标准化后的业务值。
        """
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        raise TypeError("items 必须是列表")


MemoryExtractionResult = MemoryDecisionBatch


class ChatTrace(BaseModel):
    """目的：描述聊天追踪信息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 memory_hits 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_hits 值。
    memory_hits: list[MemoryHit] = Field(default_factory=list)
    # 目的：保存 knowledge_hits 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_hits 值。
    knowledge_hits: list[str] = Field(default_factory=list)
    # 目的：保存 knowledge_evidences 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_evidences 值。
    knowledge_evidences: list[KnowledgeEvidence] = Field(default_factory=list)
    # 目的：保存 retrieval_query 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 retrieval_query 值。
    retrieval_query: str = ""
    # 目的：保存 safety_level 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_level 值。
    safety_level: str = "low"
    # 目的：保存 mcp_calls 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mcp_calls 值。
    mcp_calls: list[McpCallInfo] = Field(default_factory=list)
    # 目的：保存 prompt_version 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 prompt_version 值。
    prompt_version: str = ""
    # 目的：保存 output_contract_version 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_contract_version 值。
    output_contract_version: str = ""
    # 目的：保存 evidence_status 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 evidence_status 值。
    evidence_status: EvidenceStatus = "no_grounding"
    # 目的：保存 answer_confidence 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 answer_confidence 值。
    answer_confidence: AnswerConfidence = "low"
    # 目的：保存 answer_confidence_reason 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 answer_confidence_reason 值。
    answer_confidence_reason: str = ""
    # 目的：保存 rerank_applied 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_applied 值。
    rerank_applied: bool = False
    # 目的：保存 fallback_reason 字段，用于 ChatTrace 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fallback_reason 值。
    fallback_reason: str = ""
    # 目的：标记本次回复是否命中回答缓存。
    # 结果：调用方和日志可以区分缓存命中与实时模型调用。
    cache_hit: bool = False
    # 目的：记录本次回复命中的缓存层级。
    # 结果：便于排查 L1/L2/L3 链路和统计缓存收益。
    cache_level: CacheLevel = "none"
    # 目的：记录语义缓存命中时的相似度。
    # 结果：便于观察阈值是否过松或过严。
    cache_similarity: float | None = None


class QuestionAdvisorPayload(BaseModel):
    """目的：描述问题顾问输出的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 issue_summary 字段，用于 QuestionAdvisorPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 issue_summary 值。
    issue_summary: str = ""
    # 目的：保存 retrieval_query 字段，用于 QuestionAdvisorPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 retrieval_query 值。
    retrieval_query: str = ""
    # 目的：保存 matched_topics 字段，用于 QuestionAdvisorPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 matched_topics 值。
    matched_topics: list[str] = Field(default_factory=list)
    # 目的：保存 suggested_questions 字段，用于 QuestionAdvisorPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 suggested_questions 值。
    suggested_questions: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """目的：描述聊天响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 reply 字段，用于 ChatResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reply 值。
    reply: str
    # 目的：保存 mode 字段，用于 ChatResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: ChatMode
    # 目的：保存 trace 字段，用于 ChatResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 trace 值。
    trace: ChatTrace
    # 目的：保存 advisor 字段，用于 ChatResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 advisor 值。
    advisor: QuestionAdvisorPayload | None = None
    # 目的：保存 guest_quota_remaining 字段，用于 ChatResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 guest_quota_remaining 值。
    guest_quota_remaining: int | None = Field(default=None, description="匿名访客今日剩余可发送次数")


class ConversationHistoryMessage(BaseModel):
    """目的：描述会话历史消息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 id 字段，用于 ConversationHistoryMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 role 字段，用于 ConversationHistoryMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role 值。
    role: Literal["user", "assistant"]
    # 目的：保存 content 字段，用于 ConversationHistoryMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: str
    # 目的：保存 created_at 字段，用于 ConversationHistoryMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: datetime | None = Field(default=None, description="消息创建时间")
    # 目的：保存 advisor 字段，用于 ConversationHistoryMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 advisor 值。
    advisor: QuestionAdvisorPayload | None = Field(default=None, description="助手建议")
    # 目的：保存 assistant 回复完成状态，用于区分正常回复与用户手动中断的部分回复。
    # 结果：短期上下文和前端展示可以识别上一轮是否被中断。
    reply_status: ReplyStatus = Field(default="completed", description="助手回复状态")


class SessionSummary(BaseModel):
    """目的：会话滚动摘要，用于承接最近窗口之外的上下文。
    结果：提供 SessionSummary 的结构化能力，供业务流程复用。
    """

    # 目的：保存 summary_text 字段，用于 SessionSummary 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 summary_text 值。
    summary_text: str = Field(default="", description="会话滚动摘要正文")
    # 目的：保存 covered_message_count 字段，用于 SessionSummary 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 covered_message_count 值。
    covered_message_count: int = Field(default=0, ge=0, description="摘要已覆盖的消息数量")
    # 目的：保存 last_message_id 字段，用于 SessionSummary 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_message_id 值。
    last_message_id: str = Field(default="", description="摘要覆盖到的最后一条消息 ID")
    # 目的：保存 updated_at 字段，用于 SessionSummary 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: datetime | None = Field(default=None, description="摘要更新时间")


class ConversationContext(BaseModel):
    """目的：本轮回复使用的统一上下文。
    结果：提供 ConversationContext 的结构化能力，供业务流程复用。
    """

    # 目的：保存 session_summary 字段，用于 ConversationContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 session_summary 值。
    session_summary: SessionSummary = Field(default_factory=SessionSummary)
    # 目的：保存 recent_messages 字段，用于 ConversationContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 recent_messages 值。
    recent_messages: list[ConversationHistoryMessage] = Field(default_factory=list)
    # 目的：保存 memory_hits 字段，用于 ConversationContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_hits 值。
    memory_hits: list[MemoryHit] = Field(default_factory=list)
    # 目的：保存 knowledge_hits 字段，用于 ConversationContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_hits 值。
    knowledge_hits: list[str] = Field(default_factory=list)
    # 目的：保存 token_budget 字段，用于 ConversationContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 token_budget 值。
    token_budget: int = Field(default=1800, ge=1)
    # 目的：保存 context_version 字段，用于 ConversationContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 context_version 值。
    context_version: str = Field(default="conversation_context.v1")


class ConversationHistoryItem(BaseModel):
    """目的：描述会话历史项的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 id 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 title 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str
    # 目的：保存 preview 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 preview 值。
    preview: str
    # 目的：保存 mode 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: ChatMode
    # 目的：保存 messages 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 messages 值。
    messages: list[ConversationHistoryMessage] = Field(default_factory=list)
    # 目的：保存 latest_trace 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 latest_trace 值。
    latest_trace: ChatTrace | None = Field(default=None, description="最近一次助手回复 trace")
    # 目的：保存 active_stream_id 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 active_stream_id 值。
    active_stream_id: str | None = Field(default=None, description="当前会话进行中的流任务 ID")
    # 目的：保存 active_stream_status 字段，用于 ConversationHistoryItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 active_stream_status 值。
    active_stream_status: Literal["running", "cancelling"] | None = Field(
        default=None,
        description="当前会话进行中的流任务状态",
    )


class ConversationHistoryResponse(BaseModel):
    """目的：描述会话历史响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 user_id 字段，用于 ConversationHistoryResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: str
    # 目的：保存 conversations 字段，用于 ConversationHistoryResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversations 值。
    conversations: list[ConversationHistoryItem] = Field(default_factory=list)


class CancelStreamResponse(BaseModel):
    """目的：描述取消流任务接口的响应结构。
    结果：前后端可以围绕统一字段处理取消结果与幂等状态。
    """

    # 目的：保存 stream_id 字段，用于 CancelStreamResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 stream_id 值。
    stream_id: str = Field(default="", description="被取消的流任务 ID")
    # 目的：保存 status 字段，用于 CancelStreamResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: CancelStreamStatus = Field(default="not_found", description="取消后的任务状态")
    # 目的：保存 accepted 字段，用于 CancelStreamResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 accepted 值。
    accepted: bool = Field(default=False, description="当前请求是否真正触发了取消动作")
