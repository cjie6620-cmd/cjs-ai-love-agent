"""Redis 业务服务。"""

from __future__ import annotations

import logging
import time
from typing import Any

from .redis_client import RedisClient

logger = logging.getLogger(__name__)

_DEFAULT_RATE = 20 / 60
_DEFAULT_CAPACITY = 20

_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])

if not rate or rate <= 0 then
    return -1
end
if not capacity or capacity < 1 then
    return -1
end

local redis_time = redis.call('TIME')
local now_ms = redis_time[1] * 1000 + redis_time[2] / 1000

local bucket = redis.call('HMGET', key, 'last_tokens', 'last_time_ms')
local last_tokens = tonumber(bucket[1])
local last_time_ms = tonumber(bucket[2])

if last_tokens == nil then
    last_tokens = capacity
    last_time_ms = now_ms
end

local elapsed_ms = now_ms - last_time_ms
if elapsed_ms < 0 then
    elapsed_ms = 0
end
local elapsed_s = elapsed_ms / 1000.0
local filled_tokens = math.min(capacity, last_tokens + elapsed_s * rate)
local new_tokens = filled_tokens - 1

if new_tokens < 0 then
    return 0
end

redis.call('HMSET', key, 'last_tokens', new_tokens, 'last_time_ms', now_ms)
local ttl = math.floor(2 * capacity / rate) + 1
redis.call('EXPIRE', key, ttl)
return 1
"""


class RedisService:
    """目的：封装限流、缓存、锁和访客额度等 Redis 业务能力。
    结果：上层模块通过稳定业务方法使用 Redis，并在 Redis 不可用时按业务策略降级。
    """

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        *,
        log_startup: bool = True,
    ) -> None:
        """目的：初始化 RedisService 的底层客户端依赖。
        结果：业务方法可以复用同一个 RedisClient 执行底层命令。
        """
        self.client = redis_client or RedisClient(log_startup=log_startup)

    def check_rate_limit(
        self,
        key: str,
        *,
        rate: float = _DEFAULT_RATE,
        capacity: int = _DEFAULT_CAPACITY,
    ) -> bool:
        """目的：基于 Redis Lua 令牌桶判断请求是否允许通过。
        结果：返回 True 表示放行，False 表示触发限流。
        """
        if rate <= 0 or capacity < 1:
            logger.error("令牌桶参数异常，触发限流: key=%s, rate=%s, capacity=%s", key, rate, capacity)
            return False

        result = self.client.eval(_TOKEN_BUCKET_SCRIPT, 1, f"rate_limit:{key}", rate, capacity)
        if result is None:
            return True
        if result == 1:
            return True
        if result == -1:
            logger.error("Lua 脚本参数异常: key=%s", key)
            return False
        logger.warning("令牌桶限流触发: key=%s, rate=%.3f, capacity=%d", key, rate, capacity)
        return False

    def cache_session_context(
        self,
        session_id: str,
        context: dict[str, Any],
        *,
        ttl: int = 3600,
    ) -> bool:
        """目的：缓存会话上下文快照。
        结果：Redis 中写入可读 JSON 字符串，失败时返回 False。
        """
        return self.client.set_json(f"session_ctx:{session_id}", context, ttl=ttl)

    def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        """目的：读取会话上下文快照。
        结果：命中时返回字典，未命中、解析失败或 Redis 不可用时返回 None。
        """
        data = self.client.get_json(f"session_ctx:{session_id}")
        return data if isinstance(data, dict) else None

    def cache_response_payload(
        self,
        key: str,
        payload: dict[str, Any],
        *,
        ttl: int,
    ) -> bool:
        """目的：缓存聊天回答结果 JSON。
        结果：L1 精确缓存命中时可以直接还原 ChatResponse。
        """
        if ttl <= 0:
            return False
        return self.client.set_json(f"response_cache:exact:{key}", payload, ttl=ttl)

    def get_response_payload(self, key: str) -> dict[str, Any] | None:
        """目的：读取聊天回答结果 JSON。
        结果：未命中、脏数据或 Redis 不可用时返回 None。
        """
        data = self.client.get_json(f"response_cache:exact:{key}")
        return data if isinstance(data, dict) else None

    def delete_response_payload(self, key: str) -> bool:
        """目的：删除指定 L1 回答缓存。
        结果：缓存反序列化失败时可以清理脏数据。
        """
        return self.client.delete(f"response_cache:exact:{key}")

    def set(self, key: str, value: str, *, ttl: int | None = None) -> bool:
        """目的：写入普通字符串缓存。
        结果：返回是否写入成功。
        """
        return self.client.set(key, value, ttl=ttl)

    def get(self, key: str) -> str | None:
        """目的：读取普通字符串缓存。
        结果：返回字符串值；未命中或失败时返回 None。
        """
        return self.client.get(key)

    def delete(self, key: str) -> bool:
        """目的：删除指定 Redis 键。
        结果：返回删除命令是否成功执行。
        """
        return self.client.delete(key)

    def acquire_lock(self, key: str, *, ttl: int) -> bool | None:
        """目的：获取简单分布式锁。
        结果：返回 True 表示获取成功，False 表示锁已存在，None 表示 Redis 不可用或参数非法。
        """
        if ttl <= 0:
            return False
        if not self.client.ensure_available():
            return None
        ok = self.client.set(key, str(time.time()), ttl=ttl, nx=True)
        return ok

    def increment_with_ttl(self, key: str, *, ttl: int) -> int | None:
        """目的：原子递增计数并在首次写入时设置过期时间。
        结果：返回递增后的计数；Redis 不可用或参数非法时返回 None。
        """
        if ttl <= 0:
            return None
        count = self.client.incr(key)
        if count is None:
            return None
        if count == 1:
            self.client.expire(key, ttl)
        return count

    def append_conversation_message(
        self,
        session_id: str,
        message_data: dict[str, object],
        *,
        max_messages: int = 40,
        ttl: int = 7200,
    ) -> bool:
        """目的：追加会话消息到 Redis 热缓存列表。
        结果：Redis 中保存可读 JSON 字符串，并维护列表长度和 TTL。
        """
        return self.client.rpush_json_trim_expire(
            f"conversation:messages:{session_id}",
            message_data,
            max_items=max_messages,
            ttl=ttl,
        )

    def get_conversation_messages(
        self,
        session_id: str,
        limit: int = 40,
    ) -> list[dict[str, object]]:
        """目的：读取会话热缓存中最近的消息列表。
        结果：返回时间正序的消息字典列表，异常时返回空列表。
        """
        return self._filter_message_dicts(
            self.client.lrange_json(f"conversation:messages:{session_id}", -limit, -1)
        )

    def get_all_conversation_messages(self, session_id: str) -> list[dict[str, object]]:
        """目的：读取会话热缓存中的全部消息。
        结果：返回时间正序的消息字典列表，异常时返回空列表。
        """
        return self._filter_message_dicts(
            self.client.lrange_json(f"conversation:messages:{session_id}", 0, -1)
        )

    def delete_conversation_messages(self, session_id: str) -> bool:
        """目的：删除会话热缓存列表。
        结果：返回删除命令是否成功执行。
        """
        return self.client.delete(f"conversation:messages:{session_id}")

    def get_conversation_messages_ttl(self, session_id: str) -> int:
        """目的：读取会话热缓存剩余 TTL。
        结果：返回 Redis TTL；不存在或 Redis 不可用时返回 -2。
        """
        return self.client.ttl(f"conversation:messages:{session_id}")

    @staticmethod
    def _filter_message_dicts(items: list[Any]) -> list[dict[str, object]]:
        """目的：过滤 Redis List 解析后的消息元素。
        结果：只返回字典类型消息，避免脏数据进入上层上下文。
        """
        return [item for item in items if isinstance(item, dict)]
