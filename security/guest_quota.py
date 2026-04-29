"""匿名访客试用次数控制。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.config import Settings, get_settings

from .rate_limit import RedisService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuestQuotaResult:
    """目的：访客额度消费结果。
    结果：提供 GuestQuotaResult 的结构化能力，供业务流程复用。
    """

    # 目的：保存 allowed 字段，用于 GuestQuotaResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 allowed 值。
    allowed: bool
    # 目的：保存 remaining 字段，用于 GuestQuotaResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 remaining 值。
    remaining: int
    # 目的：保存 limit 字段，用于 GuestQuotaResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 limit 值。
    limit: int
    # 目的：保存 count 字段，用于 GuestQuotaResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 count 值。
    count: int = 0
    # 目的：保存 quota_key 字段，用于 GuestQuotaResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 quota_key 值。
    quota_key: str = ""
    # 目的：保存 reason 字段，用于 GuestQuotaResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 reason 值。
    reason: str = ""


class GuestQuotaService:
    """目的：基于 Redis 的匿名访客每日次数桶。
    结果：提供 GuestQuotaService 的结构化能力，供业务流程复用。
    """

    def __init__(
        self,
        redis_service: RedisService,
        *,
        settings: Settings | None = None,
    ) -> None:
        """目的：执行 __init__ 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        self.redis_service = redis_service
        self.settings = settings or get_settings()

    def consume(self, guest_id: str, *, ip_key: str = "") -> GuestQuotaResult:
        """目的：消费一次访客聊天额度。
        结果：完成当前实例行为并返回约定结果。
        """
        limit = max(int(self.settings.guest_daily_message_limit), 0)
        key = f"guest_quota:{guest_id}:{datetime.now(UTC).strftime('%Y%m%d')}"
        if limit <= 0:
            logger.warning("访客额度已禁用: guest_id=%s limit=%d quota_key=%s", guest_id, limit, key)
            return GuestQuotaResult(
                allowed=False,
                remaining=0,
                limit=limit,
                count=0,
                quota_key=key,
                reason="disabled",
            )

        count = self.redis_service.increment_with_ttl(key, ttl=self._seconds_until_tomorrow())
        if count is None:
            logger.warning("访客额度计数失败: guest_id=%s limit=%d quota_key=%s", guest_id, limit, key)
            return GuestQuotaResult(
                allowed=False,
                remaining=0,
                limit=limit,
                count=0,
                quota_key=key,
                reason="redis_unavailable",
            )
        if ip_key:
            ip_limit = max(int(self.settings.guest_ip_daily_message_limit), limit)
            ip_quota_key = f"guest_ip_quota:{ip_key}:{datetime.now(UTC).strftime('%Y%m%d')}"
            ip_count = self.redis_service.increment_with_ttl(
                ip_quota_key,
                ttl=self._seconds_until_tomorrow(),
            )
            if ip_count is None:
                return GuestQuotaResult(
                    allowed=False,
                    remaining=0,
                    limit=ip_limit,
                    count=0,
                    quota_key=ip_quota_key,
                    reason="redis_unavailable",
                )
            if ip_count > ip_limit:
                return GuestQuotaResult(
                    allowed=False,
                    remaining=0,
                    limit=ip_limit,
                    count=ip_count,
                    quota_key=ip_quota_key,
                    reason="ip_limit_exceeded",
                )
        remaining = max(limit - count, 0)
        if count > limit:
            return GuestQuotaResult(
                allowed=False,
                remaining=0,
                limit=limit,
                count=count,
                quota_key=key,
                reason="limit_exceeded",
            )
        return GuestQuotaResult(
            allowed=True,
            remaining=remaining,
            limit=limit,
            count=count,
            quota_key=key,
            reason="allowed",
        )

    def _seconds_until_tomorrow(self) -> int:
        """目的：执行 _seconds_until_tomorrow 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        now = datetime.now(UTC)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(int((tomorrow - now).total_seconds()), 60)
