"""应用依赖装配容器。"""

from __future__ import annotations

from dataclasses import dataclass

from agents import AgentService
from agents.stream_registry import StreamTaskRegistry
from agents.memory import ConversationContextManager, MemoryManager
from agents.workflows import CompanionGraphWorkflow, build_workflow_runtime
from core.config import Settings, get_settings
from llm.client import LlmClient
from persistence import (
    AdminRepository,
    ConversationRepository,
    KnowledgeRepository,
    MemoryAuditRepository,
    MemorySettingsRepository,
)
from rag import RagService
from rag.retriever import KnowledgeRetriever
from rag.storage import MinioClient
from security import RedisService, SafetyGuard


@dataclass(slots=True)
class AppContainer:
    """目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    # 目的：保存 settings 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 settings 值。
    settings: Settings
    # 目的：保存 redis_service 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 redis_service 值。
    redis_service: RedisService
    # 目的：保存 safety_guard 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_guard 值。
    safety_guard: SafetyGuard
    # 目的：保存 conversation_repository 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_repository 值。
    conversation_repository: ConversationRepository
    # 目的：保存 admin_repository 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 admin_repository 值。
    admin_repository: AdminRepository
    # 目的：保存 knowledge_repository 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_repository 值。
    knowledge_repository: KnowledgeRepository
    # 目的：保存 memory_manager 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_manager 值。
    memory_manager: MemoryManager
    memory_settings_repository: MemorySettingsRepository
    memory_audit_repository: MemoryAuditRepository
    # 目的：保存 conversation_context_manager 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_context_manager 值。
    conversation_context_manager: ConversationContextManager
    # 目的：保存 knowledge_retriever 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_retriever 值。
    knowledge_retriever: KnowledgeRetriever
    # 目的：保存 workflow 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 workflow 值。
    workflow: CompanionGraphWorkflow
    # 目的：保存 agent_service 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 agent_service 值。
    agent_service: AgentService
    # 目的：保存 stream_task_registry 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 stream_task_registry 值。
    stream_task_registry: StreamTaskRegistry
    # 目的：保存 rag_service 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rag_service 值。
    rag_service: RagService
    # 目的：保存 minio_client 字段，用于 AppContainer 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 minio_client 值。
    minio_client: MinioClient

    def shutdown(self) -> None:
        """目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        self.agent_service.shutdown()


def build_app_container(settings: Settings | None = None) -> AppContainer:
    """目的：构建构建应用级容器所需的数据或对象。
    结果：返回后续流程可直接消费的构建结果。
    """
    resolved_settings = settings or get_settings()
    redis_service = RedisService(log_startup=False)
    safety_guard = SafetyGuard()
    conversation_repository = ConversationRepository()
    admin_repository = AdminRepository(settings=resolved_settings)
    admin_repository.bootstrap_defaults()
    knowledge_repository = KnowledgeRepository()
    memory_settings_repository = MemorySettingsRepository()
    memory_audit_repository = MemoryAuditRepository()
    memory_manager = MemoryManager(memory_settings_repository=memory_settings_repository)
    conversation_context_manager = ConversationContextManager(
        redis_service=redis_service,
        conversation_repository=conversation_repository,
    )
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
    stream_task_registry = StreamTaskRegistry()
    rag_service = RagService()
    minio_client = MinioClient(log_startup=False)
    agent_service = AgentService(
        redis_service=redis_service,
        workflow=workflow,
        conversation_repository=conversation_repository,
        memory_manager=memory_manager,
        conversation_context_manager=conversation_context_manager,
        safety_guard=safety_guard,
        memory_settings_repository=memory_settings_repository,
        memory_audit_repository=memory_audit_repository,
        stream_task_registry=stream_task_registry,
    )
    return AppContainer(
        settings=resolved_settings,
        redis_service=redis_service,
        safety_guard=safety_guard,
        conversation_repository=conversation_repository,
        admin_repository=admin_repository,
        knowledge_repository=knowledge_repository,
        memory_manager=memory_manager,
        memory_settings_repository=memory_settings_repository,
        memory_audit_repository=memory_audit_repository,
        conversation_context_manager=conversation_context_manager,
        knowledge_retriever=knowledge_retriever,
        workflow=workflow,
        agent_service=agent_service,
        stream_task_registry=stream_task_registry,
        rag_service=rag_service,
        minio_client=minio_client,
    )
