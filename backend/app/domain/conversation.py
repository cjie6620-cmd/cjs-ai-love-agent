from dataclasses import dataclass

from ..schemas.chat import ChatMode


@dataclass(slots=True)
class ConversationContext:
    """聚合一次对话主流程中的核心上下文。"""

    session_id: str
    user_id: str
    message: str
    mode: ChatMode
