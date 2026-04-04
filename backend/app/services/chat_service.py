import json
import logging
from collections.abc import AsyncIterator

from ..infra.db.conversation_repository import ConversationRepository
from ..agents.workflows.chat_flow import CompanionWorkflow
from ..schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse

logger = logging.getLogger(__name__)


class ChatService:
    """对外提供稳定服务入口，避免路由层直接依赖具体工作流实现。"""

    def __init__(self) -> None:
        self.workflow = CompanionWorkflow()
        self.conversation_repository = ConversationRepository()

    async def reply(self, request: ChatRequest) -> ChatResponse:
        response = await self.workflow.run(request)
        self.conversation_repository.save_turn(request, response)
        return response

    async def stream_reply(self, request: ChatRequest) -> AsyncIterator[str]:
        self.conversation_repository.save_user_message(request)
        async for chunk in self.workflow.stream(request):
            response = self._extract_done_response(chunk)
            if response is not None:
                self.conversation_repository.save_assistant_message(request, response)
            yield chunk

    def list_conversations(self, user_id: str) -> ConversationHistoryResponse:
        conversations = self.conversation_repository.list_conversations(user_id)
        return ConversationHistoryResponse(user_id=user_id, conversations=conversations)

    def _extract_done_response(self, sse_payload: str) -> ChatResponse | None:
        """只在 done 事件出现时解析最终回复，其他 token 事件直接跳过。"""
        event_name = ""
        data_line = ""

        for line in sse_payload.splitlines():
            if line.startswith("event:"):
                event_name = line.replace("event:", "", 1).strip()
            elif line.startswith("data:"):
                data_line = line.replace("data:", "", 1).strip()

        if event_name != "done" or not data_line:
            return None

        try:
            return ChatResponse.model_validate(json.loads(data_line))
        except (ValueError, TypeError) as exc:
            logger.warning("解析 SSE done 事件失败，跳过持久化: %s", exc)
            return None
