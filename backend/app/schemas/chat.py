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
