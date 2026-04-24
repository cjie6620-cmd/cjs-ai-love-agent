"""应用依赖装配容器。"""

from __future__ import annotations

from dataclasses import dataclass

from agents import AgentService
from agents.memory import MemoryManager, SessionMemoryManager
from agents.workflows import CompanionGraphWorkflow, build_workflow_runtime
from core.config import Settings, get_settings
from llm.client import LlmClient
from persistence import ConversationRepository
from rag import RagService
from rag.retriever import KnowledgeRetriever
from rag.storage import MinioClient
from security import RedisService, SafetyGuard


@dataclass(slots=True)
class AppContainer:
    """集中持有应用运行所需的核心服务。

    目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    settings: Settings
    redis_service: RedisService
    safety_guard: SafetyGuard
    conversation_repository: ConversationRepository
    memory_manager: MemoryManager
    session_memory: SessionMemoryManager
    knowledge_retriever: KnowledgeRetriever
    workflow: CompanionGraphWorkflow
    agent_service: AgentService
    rag_service: RagService
    minio_client: MinioClient

    def shutdown(self) -> None:
        """关闭并释放相关资源。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        self.agent_service.shutdown()


def build_app_container(settings: Settings | None = None) -> AppContainer:
    """构建应用级容器。
    
    目的：构建构建应用级容器所需的数据或对象。
    结果：返回后续流程可直接消费的构建结果。
    """
    resolved_settings = settings or get_settings()
    redis_service = RedisService(log_startup=False)
    safety_guard = SafetyGuard()
    conversation_repository = ConversationRepository()
    memory_manager = MemoryManager()
    session_memory = SessionMemoryManager(redis_service=redis_service)
    knowledge_retriever = KnowledgeRetriever()
    workflow = CompanionGraphWorkflow(
        runtime=build_workflow_runtime(
            settings=resolved_settings,
            llm_client_factory=LlmClient,
            memory_manager=memory_manager,
            knowledge_retriever=knowledge_retriever,
            safety_guard=safety_guard,
        )
    )
    rag_service = RagService()
    minio_client = MinioClient(log_startup=False)
    agent_service = AgentService(
        redis_service=redis_service,
        workflow=workflow,
        conversation_repository=conversation_repository,
        memory_manager=memory_manager,
        session_memory=session_memory,
        safety_guard=safety_guard,
    )
    return AppContainer(
        settings=resolved_settings,
        redis_service=redis_service,
        safety_guard=safety_guard,
        conversation_repository=conversation_repository,
        memory_manager=memory_manager,
        session_memory=session_memory,
        knowledge_retriever=knowledge_retriever,
        workflow=workflow,
        agent_service=agent_service,
        rag_service=rag_service,
        minio_client=minio_client,
    )
