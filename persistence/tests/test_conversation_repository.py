from unittest.mock import MagicMock

from persistence.conversation_repository import ConversationRepository


def _make_repository() -> ConversationRepository:
    """make repository 测试辅助方法。
    
    目的：为当前测试文件提供公共构造、准备或提取逻辑。
    结果：减少重复测试代码，提升测试可读性和维护性。
    """
    return ConversationRepository(session_factory=MagicMock())


def test_deserialize_trace_requires_standard_trace_wrapper():
    """验证 deserialize trace requires standard trace wrapper。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    repository = _make_repository()

    result = repository._deserialize_trace(
        {
            "memory_hits": [{"content": "旧格式", "score": 0.8, "chunk_id": "legacy"}],
            "knowledge_hits": ["k1"],
            "retrieval_query": "q",
            "safety_level": "medium",
        }
    )

    assert result.memory_hits == []
    assert result.knowledge_hits == []
    assert result.retrieval_query == ""
    assert result.safety_level == "low"


def test_deserialize_trace_uses_only_current_memory_hit_schema():
    """验证 deserialize trace uses only current memory hit schema。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    repository = _make_repository()

    result = repository._deserialize_trace(
        {
            "trace": {
                "memory_hits": [
                    {"content": "当前格式", "score": 0.9, "chunk_id": "chunk-1"},
                    "legacy-string",
                ],
                "knowledge_hits": ["k1"],
                "retrieval_query": "query",
                "safety_level": "medium",
            }
        }
    )

    assert result.memory_hits == [
        {"content": "当前格式", "score": 0.9, "chunk_id": "chunk-1"}
    ]
    assert result.knowledge_hits == ["k1"]
    assert result.retrieval_query == "query"
    assert result.safety_level == "medium"
