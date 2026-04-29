"""长期记忆隐私治理策略。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contracts.chat import MemoryDecision


@dataclass(frozen=True)
class MemoryPolicyResult:
    """目的：表达长期记忆治理拦截结果。
    结果：调用方可以按 allowed 决定继续写入或跳过，并记录审计原因。
    """

    allowed: bool
    reason_code: str = "allowed"
    matched_types: tuple[str, ...] = ()


class MemoryPolicyService:
    """目的：在模型判断之外提供确定性隐私拦截。
    结果：手机号、身份证、银行卡、密码密钥、邮箱、精确住址不会进入长期记忆链路。
    """

    _EMAIL_PATTERN = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )
    _CN_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
    _CN_ID_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d{15}|\d{17}[\dXx])(?!\d)")
    _BANK_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){16,19}(?!\d)")
    _SECRET_PATTERN = re.compile(
        r"(密码|口令|密钥|api[_\s-]?key|access[_\s-]?key|secret|token|password)"
        r"\s*[:：=是为]\s*\S{4,}",
        re.IGNORECASE,
    )
    _ADDRESS_PATTERN = re.compile(
        r"(住址|地址|住在|我家在|公司在|学校在).{0,24}"
        r"(省|市|区|县|镇|街道|路|弄|号|栋|单元|室|小区)",
    )

    _PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("email", _EMAIL_PATTERN),
        ("phone", _CN_PHONE_PATTERN),
        ("id_card", _CN_ID_CARD_PATTERN),
        ("bank_card", _BANK_CARD_PATTERN),
        ("secret", _SECRET_PATTERN),
        ("address", _ADDRESS_PATTERN),
    )

    def evaluate_raw_text(self, *, user_message: str, assistant_reply: str) -> MemoryPolicyResult:
        """目的：写 Outbox 前检查原始对话文本。
        结果：命中敏感信息时直接跳过候选事件。
        """
        return self._evaluate_text(f"{user_message}\n{assistant_reply}")

    def evaluate_decision(self, decision: MemoryDecision) -> MemoryPolicyResult:
        """目的：模型抽取后再次检查规范化记忆正文。
        结果：防止模型把敏感信息整理后写入 pgvector。
        """
        if not decision.should_store:
            return MemoryPolicyResult(allowed=True)
        return self._evaluate_text(decision.memory_text)

    def _evaluate_text(self, text: str) -> MemoryPolicyResult:
        normalized = str(text or "").strip()
        if not normalized:
            return MemoryPolicyResult(allowed=True)

        matched = tuple(name for name, pattern in self._PATTERNS if pattern.search(normalized))
        if matched:
            return MemoryPolicyResult(
                allowed=False,
                reason_code="sensitive_personal_information",
                matched_types=matched,
            )
        return MemoryPolicyResult(allowed=True)
