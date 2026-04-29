"""匿名访客额度服务测试。"""

from __future__ import annotations

from security.guest_quota import GuestQuotaService


class _FakeRedisService:
    """用于测试 GuestQuotaService 的最小 Redis 假实现。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def increment_with_ttl(self, key: str, *, ttl: int) -> int | None:
        if ttl <= 0:
            return None
        current = self.counts.get(key, 0) + 1
        self.counts[key] = current
        return current


class _FakeSettings:
    """只暴露访客额度配置的最小设置对象。"""

    def __init__(self, *, limit: int) -> None:
        self.guest_daily_message_limit = limit


def test_guest_quota_limit_one_blocks_second_message() -> None:
    """limit=1 时第一条放行，第二条拦截。"""
    service = GuestQuotaService(
        _FakeRedisService(),
        settings=_FakeSettings(limit=1),
    )

    first = service.consume("guest-quota-unit")
    second = service.consume("guest-quota-unit")

    assert first.allowed is True
    assert first.limit == 1
    assert first.count == 1
    assert first.remaining == 0
    assert first.reason == "allowed"
    assert second.allowed is False
    assert second.limit == 1
    assert second.count == 2
    assert second.remaining == 0
    assert second.reason == "limit_exceeded"


def test_guest_quota_disabled_rejects_immediately() -> None:
    """limit<=0 时直接返回禁用状态。"""
    service = GuestQuotaService(
        _FakeRedisService(),
        settings=_FakeSettings(limit=0),
    )

    result = service.consume("guest-quota-disabled")

    assert result.allowed is False
    assert result.limit == 0
    assert result.count == 0
    assert result.remaining == 0
    assert result.reason == "disabled"
