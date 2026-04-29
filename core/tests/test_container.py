"""容器装配测试。"""

from __future__ import annotations

from types import SimpleNamespace

import core.container as container_module


def test_build_app_container_wires_major_services(monkeypatch) -> None:
    """验证 build app container wires major services。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    settings = container_module.Settings()

    redis_service = SimpleNamespace(name="redis")
    safety_guard = SimpleNamespace(name="safety")
    conversation_repository = SimpleNamespace(name="conversation_repo")
    knowledge_repository = SimpleNamespace(name="knowledge_repo")
    memory_settings_repository = SimpleNamespace(name="memory_settings")
    memory_audit_repository = SimpleNamespace(name="memory_audit")
    memory_manager = SimpleNamespace(name="memory")
    conversation_context_manager = SimpleNamespace(name="conversation_context_manager")
    knowledge_retriever = SimpleNamespace(name="knowledge")
    workflow = SimpleNamespace(name="workflow")
    stream_task_registry = SimpleNamespace(name="stream_task_registry")
    rag_service = SimpleNamespace(name="rag")
    minio_client = SimpleNamespace(name="minio")
    runtime = SimpleNamespace(name="runtime")

    captured: dict[str, object] = {}

    class FakeAdminRepository:
        def __init__(self, **kwargs) -> None:
            captured["admin_repo_kwargs"] = kwargs
            self.bootstrap_called = False

        def bootstrap_defaults(self) -> None:
            self.bootstrap_called = True

    class FakeAgentService:
        def __init__(self, **kwargs) -> None:
            captured["agent_kwargs"] = kwargs
            self.shutdown_called = False

        def shutdown(self) -> None:
            self.shutdown_called = True

    def fake_memory_manager_factory(**kwargs):
        captured["memory_kwargs"] = kwargs
        return memory_manager

    monkeypatch.setattr(container_module, "RedisService", lambda *args, **kwargs: redis_service)
    monkeypatch.setattr(container_module, "SafetyGuard", lambda: safety_guard)
    monkeypatch.setattr(
        container_module,
        "ConversationRepository",
        lambda: conversation_repository,
    )
    monkeypatch.setattr(container_module, "AdminRepository", FakeAdminRepository)
    monkeypatch.setattr(container_module, "KnowledgeRepository", lambda: knowledge_repository)
    monkeypatch.setattr(container_module, "MemorySettingsRepository", lambda: memory_settings_repository)
    monkeypatch.setattr(container_module, "MemoryAuditRepository", lambda: memory_audit_repository)
    monkeypatch.setattr(
        container_module,
        "MemoryManager",
        fake_memory_manager_factory,
    )
    monkeypatch.setattr(
        container_module,
        "ConversationContextManager",
        lambda redis_service, conversation_repository: conversation_context_manager,
    )
    monkeypatch.setattr(
        container_module,
        "KnowledgeRetriever",
        lambda: knowledge_retriever,
    )
    monkeypatch.setattr(container_module, "RagService", lambda: rag_service)
    monkeypatch.setattr(container_module, "MinioClient", lambda *args, **kwargs: minio_client)
    monkeypatch.setattr(container_module, "StreamTaskRegistry", lambda: stream_task_registry)

    def fake_build_runtime(**kwargs):
        captured["runtime_kwargs"] = kwargs
        return runtime

    def fake_workflow_factory(*, runtime):
        captured["workflow_runtime"] = runtime
        return workflow

    monkeypatch.setattr(container_module, "build_workflow_runtime", fake_build_runtime)
    monkeypatch.setattr(container_module, "CompanionGraphWorkflow", fake_workflow_factory)
    monkeypatch.setattr(container_module, "AgentService", FakeAgentService)

    container = container_module.build_app_container(settings)

    assert container.settings is settings
    assert container.redis_service is redis_service
    assert container.safety_guard is safety_guard
    assert container.conversation_repository is conversation_repository
    assert container.knowledge_repository is knowledge_repository
    assert container.admin_repository.bootstrap_called is True
    assert container.memory_settings_repository is memory_settings_repository
    assert container.memory_audit_repository is memory_audit_repository
    assert container.memory_manager is memory_manager
    assert container.conversation_context_manager is conversation_context_manager
    assert container.knowledge_retriever is knowledge_retriever
    assert container.workflow is workflow
    assert container.stream_task_registry is stream_task_registry
    assert container.rag_service is rag_service
    assert container.minio_client is minio_client

    assert captured["workflow_runtime"] is runtime
    assert captured["memory_kwargs"] == {
        "memory_settings_repository": memory_settings_repository,
    }
    assert captured["runtime_kwargs"] == {
        "settings": settings,
        "llm_client_factory": container_module.LlmClient,
        "memory_manager": memory_manager,
        "knowledge_retriever": knowledge_retriever,
        "safety_guard": safety_guard,
    }
    assert captured["agent_kwargs"] == {
        "redis_service": redis_service,
        "workflow": workflow,
        "conversation_repository": conversation_repository,
        "memory_manager": memory_manager,
        "conversation_context_manager": conversation_context_manager,
        "safety_guard": safety_guard,
        "memory_settings_repository": memory_settings_repository,
        "memory_audit_repository": memory_audit_repository,
        "stream_task_registry": stream_task_registry,
    }

    container.shutdown()
    assert container.agent_service.shutdown_called is True
