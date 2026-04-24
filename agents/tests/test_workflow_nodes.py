from contracts.chat import KnowledgeEvidence

from agents.workflows.nodes import build_local_chat_reply


def test_build_local_chat_reply_populates_deterministic_fields() -> None:
    """普通聊天应由本地规则补齐 ChatReplyModel 字段。"""
    result = build_local_chat_reply(
        reply_text="先别急，我们把最想说的话整理出来。",
        mode="companion",
        evidence_status="grounded",
        used_memory=True,
        safety_level="medium",
        knowledge_evidences=[
            KnowledgeEvidence(evidence_id="K1", snippet="证据1"),
            KnowledgeEvidence(evidence_id="K2", snippet="证据2"),
        ],
    )

    assert result.reply_text.startswith("先别急")
    assert result.intent == "support"
    assert result.tone == "warm"
    assert result.grounded_by_knowledge is True
    assert result.used_memory is True
    assert result.needs_followup is False
    assert result.used_evidence_ids == ["K1", "K2"]
    assert result.safety_notes == ["保持边界清晰，避免替代真实关系。"]


def test_build_local_chat_reply_marks_no_grounding_fallback() -> None:
    """没有可靠证据时应给出默认 fallback_reason。"""
    result = build_local_chat_reply(
        reply_text="我们先别急着下结论，你可以先说说最近最别扭的一次互动。",
        mode="advice",
        evidence_status="no_grounding",
        used_memory=False,
        safety_level="low",
        knowledge_evidences=[],
    )

    assert result.intent == "advice"
    assert result.tone == "direct"
    assert result.grounded_by_knowledge is False
    assert result.needs_followup is True
    assert result.fallback_reason == "no_grounding"
    assert result.used_evidence_ids == []
