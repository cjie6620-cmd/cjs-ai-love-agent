from ..agents.workflows.chat_flow import CompanionWorkflow
from ..schemas.chat import ChatRequest, ChatResponse


class ChatService:
    """对外提供稳定服务入口，避免路由层直接依赖具体工作流实现。"""

    def __init__(self) -> None:
        self.workflow = CompanionWorkflow()

    async def reply(self, request: ChatRequest) -> ChatResponse:
        return await self.workflow.run(request)
