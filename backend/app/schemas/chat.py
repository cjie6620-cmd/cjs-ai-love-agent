from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ChatMode = Literal["companion", "advice", "style_clone", "soothing"]


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="会话唯一标识")
    user_id: str = Field(..., description="用户唯一标识")
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入消息")
    mode: ChatMode = Field(default="companion", description="当前对话模式")


class ChatTrace(BaseModel):
    memory_hits: list[str] = Field(default_factory=list)
    knowledge_hits: list[str] = Field(default_factory=list)
    safety_level: str = "low"


class ChatResponse(BaseModel):
    reply: str
    mode: ChatMode
    trace: ChatTrace


class ConversationHistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = Field(default=None, description="消息创建时间")


class ConversationHistoryItem(BaseModel):
    id: str
    title: str
    preview: str
    mode: ChatMode
    messages: list[ConversationHistoryMessage] = Field(default_factory=list)
    latest_trace: ChatTrace | None = Field(default=None, description="最近一次助手回复 trace")


class ConversationHistoryResponse(BaseModel):
    user_id: str
    conversations: list[ConversationHistoryItem] = Field(default_factory=list)
