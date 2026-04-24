"""容器装配测试。"""

from __future__ import annotations

from types import SimpleNamespace

import core.container as container_module


def test_build_app_container_wires_major_services(monkeypatch) -> None:
    """验证 build app container wires major services。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    settings = container_module.Settings(langgraph_use_checkpointer=False)

    redis_service = SimpleNamespace(name="redis")
    safety_guard = SimpleNamespace(name="safety")
    conversation_repository = SimpleNamespace(name="conversation_repo")
    memory_manager = SimpleNamespace(name="memory")
    session_memory = SimpleNamespace(name="session_memory")
    knowledge_retriever = SimpleNamespace(name="knowledge")
    workflow = SimpleNamespace(name="workflow")
    rag_service = SimpleNamespace(name="rag")
    minio_client = SimpleNamespace(name="minio")
    runtime = SimpleNamespace(name="runtime")

    captured: dict[str, object] = {}

    class FakeAgentService:
        def __init__(self, **kwargs) -> None:
            captured["agent_kwargs"] = kwargs
            self.shutdown_called = False

        def shutdown(self) -> None:
            self.shutdown_called = True

    monkeypatch.setattr(container_module, "RedisService", lambda *args, **kwargs: redis_service)
    monkeypatch.setattr(container_module, "SafetyGuard", lambda: safety_guard)
    monkeypatch.setattr(
        container_module,
        "ConversationRepository",
        lambda: conversation_repository,
    )
    monkeypatch.setattr(container_module, "MemoryManager", lambda: memory_manager)
    monkeypatch.setattr(
        container_module,
        "SessionMemoryManager",
        lambda redis_service: session_memory,
    )
    monkeypatch.setattr(
        container_module,
        "KnowledgeRetriever",
        lambda: knowledge_retriever,
    )
    monkeypatch.setattr(container_module, "RagService", lambda: rag_service)
    monkeypatch.setattr(container_module, "MinioClient", lambda *args, **kwargs: minio_client)

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
    assert container.memory_manager is memory_manager
    assert container.session_memory is session_memory
    assert container.knowledge_retriever is knowledge_retriever
    assert container.workflow is workflow
    assert container.rag_service is rag_service
    assert container.minio_client is minio_client

    assert captured["workflow_runtime"] is runtime
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
        "session_memory": session_memory,
        "safety_guard": safety_guard,
    }

    container.shutdown()
    assert container.agent_service.shutdown_called is True
