"""聊天与工作流相关的共享契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, Field, field_validator

ChatMode = Literal["companion", "advice", "style_clone", "soothing"]
EvidenceStatus = Literal["grounded", "weak_grounding", "no_grounding"]
MemoryType = Literal["event", "preference", "profile_summary", "none"]
AnswerConfidence = Literal["high", "medium", "low"]
MemoryMergeStrategy = Literal["insert", "replace", "append", "skip"]


class MemoryHit(TypedDict):
    """长期记忆命中项。
    
    目的：描述长期记忆命中项的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    content: str
    score: float
    chunk_id: str


class ChatRequest(BaseModel):
    """聊天请求。
    
    目的：描述聊天请求的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    session_id: str = Field(..., description="会话唯一标识")
    user_id: str = Field(..., description="用户唯一标识")
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入消息")
    mode: ChatMode = Field(default="companion", description="当前对话模式")


class McpCallInfo(BaseModel):
    """MCP 工具调用追踪信息。
    
    目的：描述MCP 工具调用追踪信息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    server_label: str = Field(description="MCP 服务器标签")
    tool_name: str = Field(description="被调用的工具名称")
    status: Literal["success", "error", "skipped"] = Field(description="调用状态")
    duration_ms: int = Field(description="调用耗时（毫秒）")
    input_summary: str = Field(default="", description="输入摘要")
    output_summary: str = Field(default="", description="输出摘要")
    error_message: str = Field(default="", description="错误信息")


class KnowledgeEvidence(BaseModel):
    """知识证据对象。"""

    evidence_id: str = Field(default="", description="证据编号，供模型和 trace 对齐")
    chunk_id: str = Field(default="", description="命中的子块 ID")
    parent_id: str = Field(default="", description="父块 ID")
    title: str = Field(default="", description="文档标题")
    source: str = Field(default="", description="来源")
    heading_path: str = Field(default="", description="章节路径")
    snippet: str = Field(default="", description="证据摘要")
    dense_score: float | None = Field(default=None, description="向量召回得分")
    bm25_score: float | None = Field(default=None, description="BM25 召回得分")
    fusion_score: float | None = Field(default=None, description="融合得分")
    rerank_score: float | None = Field(default=None, description="重排得分")
    rank: int = Field(default=0, description="最终排序位置")
    locator: str = Field(default="", description="定位信息，如文件名/章节")


class ChatReplyModel(BaseModel):
    """结构化聊天回复。
    
    目的：描述结构化聊天回复的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    reply_text: str = Field(default="", description="最终发送给用户的文本")
    intent: str = Field(default="support", description="回复意图")
    tone: str = Field(default="warm", description="回复语气")
    grounded_by_knowledge: bool = Field(default=False, description="是否基于知识证据")
    used_memory: bool = Field(default=False, description="是否吸收长期记忆")
    needs_followup: bool = Field(default=False, description="是否建议下一轮追问")
    fallback_reason: str = Field(default="", description="兜底原因")
    safety_notes: list[str] = Field(default_factory=list, description="安全备注")
    used_evidence_ids: list[str] = Field(
        default_factory=list,
        description="本次回答实际使用到的证据编号",
    )

    @field_validator("reply_text", mode="before")
    @classmethod
    def normalize_reply_text(cls, value: object) -> str:
        """标准化 reply_text 字段输入。
        
        目的：标准化 reply_text 字段输入，统一边界值和格式。
        结果：返回清洗后的结果，避免脏数据影响后续逻辑。
        """
        return str(value or "").strip()


class MemoryDecision(BaseModel):
    """长期记忆结构化提取结果。

    目的：约束后台大模型对单轮对话的长期记忆分析输出，统一存储价值、治理键和合并策略。
    结果：Celery 记忆任务可以基于该结构完成跳过、新增、替换或合并写入。
    """

    should_store: bool = Field(default=False, description="是否写入长期记忆")
    memory_type: MemoryType = Field(default="none", description="记忆类型")
    memory_text: str = Field(default="", description="归一化后的记忆文本")
    canonical_key: str = Field(default="", description="同类记忆的稳定治理键")
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="长期价值重要性评分")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    merge_strategy: MemoryMergeStrategy = Field(default="skip", description="同类记忆命中后的合并策略")
    reason_code: str = Field(default="no_value", description="原因编码")

    @field_validator("memory_text", mode="before")
    @classmethod
    def normalize_memory_text(cls, value: object) -> str:
        """标准化记忆文本。

        目的：清理模型输出中的空值和首尾空白，避免脏文本进入治理链路。
        结果：返回可继续校验和持久化的记忆文本。
        """
        return str(value or "").strip()

    @field_validator("canonical_key", mode="before")
    @classmethod
    def normalize_canonical_key(cls, value: object) -> str:
        """标准化治理键。

        目的：收敛模型输出的治理键格式，保证同类记忆可以稳定去重。
        结果：返回小写、去空白的 canonical_key。
        """
        return str(value or "").strip().lower()

    @field_validator("reason_code", mode="before")
    @classmethod
    def normalize_reason_code(cls, value: object) -> str:
        """标准化原因编码。

        目的：清理模型输出中的空值和首尾空白，保证跳过或保存原因可观测。
        结果：返回稳定的 reason_code。
        """
        return str(value or "no_value").strip() or "no_value"

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, value: MemoryType, info) -> MemoryType:
        """校验记忆类型。

        目的：根据 should_store 约束 memory_type，避免跳过结果携带可写入类型。
        结果：返回与写入决策一致的记忆类型。
        """
        should_store = bool(info.data.get("should_store", False))
        if should_store:
            return "event" if value == "none" else value
        return "none"

    @field_validator("memory_text")
    @classmethod
    def validate_memory_text(cls, value: str, info) -> str:
        """校验记忆文本。

        目的：限制可写入文本长度，并在跳过时清空文本。
        结果：返回符合长期记忆存储约束的文本。
        """
        should_store = bool(info.data.get("should_store", False))
        if should_store:
            return value[:180]
        return ""

    @field_validator("canonical_key")
    @classmethod
    def validate_canonical_key(cls, value: str, info) -> str:
        """校验治理键。

        目的：保证可写入记忆具备去重合并所需的稳定键，跳过结果不保留治理键。
        结果：返回可用于查询的 canonical_key。
        """
        should_store = bool(info.data.get("should_store", False))
        if not should_store:
            return ""
        return value[:96] or "memory:general"

    @field_validator("merge_strategy")
    @classmethod
    def validate_merge_strategy(cls, value: MemoryMergeStrategy, info) -> MemoryMergeStrategy:
        """校验合并策略。

        目的：保证跳过结果不会触发写入策略，写入结果默认按新增处理。
        结果：返回与 should_store 一致的合并策略。
        """
        should_store = bool(info.data.get("should_store", False))
        if not should_store:
            return "skip"
        return "insert" if value == "skip" else value


MemoryExtractionResult = MemoryDecision


class ChatTrace(BaseModel):
    """聊天追踪信息。
    
    目的：描述聊天追踪信息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    memory_hits: list[MemoryHit] = Field(default_factory=list)
    knowledge_hits: list[str] = Field(default_factory=list)
    knowledge_evidences: list[KnowledgeEvidence] = Field(default_factory=list)
    retrieval_query: str = ""
    safety_level: str = "low"
    mcp_calls: list[McpCallInfo] = Field(default_factory=list)
    prompt_version: str = ""
    output_contract_version: str = ""
    evidence_status: EvidenceStatus = "no_grounding"
    answer_confidence: AnswerConfidence = "low"
    answer_confidence_reason: str = ""
    rerank_applied: bool = False
    fallback_reason: str = ""


class QuestionAdvisorPayload(BaseModel):
    """问题顾问输出。
    
    目的：描述问题顾问输出的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    issue_summary: str = ""
    retrieval_query: str = ""
    matched_topics: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """聊天响应。
    
    目的：描述聊天响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    reply: str
    mode: ChatMode
    trace: ChatTrace
    advisor: QuestionAdvisorPayload | None = None


class ConversationHistoryMessage(BaseModel):
    """会话历史消息。
    
    目的：描述会话历史消息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = Field(default=None, description="消息创建时间")
    advisor: QuestionAdvisorPayload | None = Field(default=None, description="助手建议")


class ConversationHistoryItem(BaseModel):
    """会话历史项。
    
    目的：描述会话历史项的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    id: str
    title: str
    preview: str
    mode: ChatMode
    messages: list[ConversationHistoryMessage] = Field(default_factory=list)
    latest_trace: ChatTrace | None = Field(default=None, description="最近一次助手回复 trace")


class ShortTermMessage(BaseModel):
    """短期记忆单条消息。
    
    目的：描述短期记忆单条消息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = Field(default=None, description="消息创建时间")
    advisor: QuestionAdvisorPayload | None = Field(default=None, description="助手建议")


class ConversationHistoryResponse(BaseModel):
    """会话历史响应。
    
    目的：描述会话历史响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    user_id: str
    conversations: list[ConversationHistoryItem] = Field(default_factory=list)
