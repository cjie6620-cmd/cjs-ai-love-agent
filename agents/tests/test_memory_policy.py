from __future__ import annotations

from agents.memory_policy import MemoryPolicyService
from contracts.chat import MemoryDecision


def test_memory_policy_allows_stable_preference() -> None:
    policy = MemoryPolicyService()

    result = policy.evaluate_raw_text(
        user_message="我比较喜欢你以后回复短一点，不要太啰嗦。",
        assistant_reply="好的，我以后会尽量简洁一点。",
    )

    assert result.allowed is True


def test_memory_policy_blocks_sensitive_raw_text() -> None:
    policy = MemoryPolicyService()

    result = policy.evaluate_raw_text(
        user_message="我的手机号是13800138000，密码是 abc12345",
        assistant_reply="好的",
    )

    assert result.allowed is False
    assert "phone" in result.matched_types
    assert "secret" in result.matched_types


def test_memory_policy_blocks_sensitive_decision_text() -> None:
    policy = MemoryPolicyService()
    decision = MemoryDecision(
        should_store=True,
        memory_type="profile_summary",
        memory_text="用户身份证号是110101199003070011",
        canonical_key="profile:id_card",
        importance_score=0.9,
        confidence=0.95,
        merge_strategy="replace",
        reason_code="explicit_identity",
    )

    result = policy.evaluate_decision(decision)

    assert result.allowed is False
    assert "id_card" in result.matched_types
