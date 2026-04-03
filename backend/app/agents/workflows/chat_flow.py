from ...domain.conversation import ConversationContext
from ...infra.llm.client import LlmClient
from ...memory.manager import MemoryManager
from ...rag.retriever import KnowledgeRetriever
from ...safety.guardrails import SafetyGuard
from ...schemas.chat import ChatRequest, ChatResponse, ChatTrace


class CompanionWorkflow:
    """当前先用可控的串行流程占位，后续可平滑演进到 LangGraph 状态图。"""

    def __init__(self) -> None:
        self.memory_manager = MemoryManager()
        self.knowledge_retriever = KnowledgeRetriever()
        self.safety_guard = SafetyGuard()
        self.llm_client = LlmClient()

    async def run(self, request: ChatRequest) -> ChatResponse:
        context = ConversationContext(
            session_id=request.session_id,
            user_id=request.user_id,
            message=request.message,
            mode=request.mode,
        )

        safety_level = self.safety_guard.inspect_input(context.message)
        memory_hits = self.memory_manager.recall(context.user_id)
        knowledge_hits = (
            self.knowledge_retriever.search(context.message)
            if context.mode in {"advice", "style_clone"}
            else []
        )

        reply = await self._build_reply(context, memory_hits, knowledge_hits, safety_level)
        reply = self.safety_guard.inspect_output(reply, safety_level)

        return ChatResponse(
            reply=reply,
            mode=request.mode,
            trace=ChatTrace(
                memory_hits=memory_hits,
                knowledge_hits=knowledge_hits,
                safety_level=safety_level,
            ),
        )

    async def _build_reply(
        self,
        context: ConversationContext,
        memory_hits: list[str],
        knowledge_hits: list[str],
        safety_level: str,
    ) -> str:
        memory_hint = memory_hits[0] if memory_hits else "暂未命中长期记忆"
        knowledge_hint = knowledge_hits[0] if knowledge_hits else "当前未触发知识检索"

        if safety_level == "high":
            return "我能感受到你现在情绪很重，我们先把节奏放慢一点。如果你愿意，我可以先陪你把发生的事理清楚。"

        system_prompt = self._build_system_prompt(context.mode)
        user_prompt = (
            f"用户消息：{context.message}\n"
            f"长期记忆：{memory_hint}\n"
            f"知识检索：{knowledge_hint}\n"
            "请给出自然、简洁、可执行的中文回复。"
        )
        return await self.llm_client.generate(system_prompt, user_prompt)

    def _build_system_prompt(self, mode: str) -> str:
        mode_instructions = {
            "companion": "你是温和、稳定、边界清晰的情感陪伴助手。",
            "advice": "你是擅长恋爱沟通拆解的顾问，回答要具体、可执行。",
            "style_clone": "你需要参考风格信息组织语气，但不能突破安全边界。",
            "soothing": "你要先共情、再陪伴，避免说教和强刺激表达。",
        }
        return (
            "你是 AI Love Agent 的核心对话模型。\n"
            "回答要求：简洁、自然、像真人沟通，但不能过度依赖、不能越界。\n"
            f"当前模式：{mode_instructions.get(mode, mode_instructions['companion'])}"
        )
