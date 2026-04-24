"""Redis 业务逻辑服务：封装速率限制、会话缓存和通用缓存操作。

目的：提供基于 Redis 的业务功能封装，包括 API 速率限制和会话上下文缓存。
结果：提供统一的 Redis 操作接口，支持 API 速率限制和会话上下文缓存。
Redis 不可用时所有方法降级处理：速率限制放行，缓存读取返回空值，不阻塞主流程。

中文处理策略：
- Redis 连接使用二进制模式（decode_responses=False），避免 redis-py 的隐式解码破坏 UTF-8
- JSON 序列化统一使用 ensure_ascii=False，确保中文字符直接写入而非转义为 \\uXXXX
- 所有字符串存取均显式指定 UTF-8 编码/解码，防止平台差异导致的乱码
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from redis import ConnectionError as RedisConnectionError
from redis import Redis

from core.config import get_settings

logger = logging.getLogger(__name__)

# 速率限制默认配置（令牌桶参数）
_DEFAULT_RATE = 20 / 60  # 每秒补充 token 数：20 / 60 ≈ 0.333
_DEFAULT_CAPACITY = 20  # 桶容量，即最大突发请求数

# Redis 数据编码
_REDIS_ENCODING = "utf-8"


def _mask_redis_url(url: str) -> str:
    """脱敏 Redis URL 中的密码，避免日志泄露敏感信息。"""
    return re.sub(r"(://[^@]*:)[^@]*(@)", r"\1***\2", url)

# 令牌桶 Lua 脚本：原子实现令牌桶扣减逻辑
# KEYS[1] = rate_key（存储令牌桶状态的 Hash）
# ARGV[1] = rate（每秒补充令牌数）
# ARGV[2] = capacity（桶容量）
# 注意：now_ms 不再由应用侧传入，改由 Redis TIME 命令获取服务端时间，
# 避免多实例时钟漂移导致的令牌误判（elapsed 可能为负数）。
# 返回值: 1 = 获取令牌成功，0 = 令牌不足限流，-1 = 参数非法
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])

-- 参数校验：rate 必须为正数，capacity 必须 >= 1，防止配置错误静默放行
if not rate or rate <= 0 then
    return -1
end
if not capacity or capacity < 1 then
    return -1
end

-- 取 Redis 服务端时间（毫秒），保证多实例时钟一致
local redis_time = redis.call('TIME')
local now_ms = redis_time[1] * 1000 + redis_time[2] / 1000

-- 取令牌桶状态：last_tokens（上一次剩余令牌数）, last_time_ms（上次更新时间戳）
local bucket = redis.call('HMGET', key, 'last_tokens', 'last_time_ms')
local last_tokens = tonumber(bucket[1])
local last_time_ms = tonumber(bucket[2])

-- 初始化：桶初始为满桶
if last_tokens == nil then
    last_tokens = capacity
    last_time_ms = now_ms
end

-- 计算时间差，按 rate 补充令牌，不超过 capacity
local elapsed_ms = now_ms - last_time_ms
-- 防御：elapsed_ms 为负（时钟回拨）时视为 0，防止令牌被错误回退
if elapsed_ms < 0 then
    elapsed_ms = 0
end
local elapsed_s = elapsed_ms / 1000.0
local filled_tokens = math.min(capacity, last_tokens + elapsed_s * rate)
local new_tokens = filled_tokens - 1  -- 扣减本次请求的 1 个令牌

if new_tokens < 0 then
    -- 令牌不足，拒绝请求（桶状态不变，不更新时间戳）
    return 0
end

-- 更新桶状态：写入新令牌数和当前时间戳
redis.call('HMSET', key, 'last_tokens', new_tokens, 'last_time_ms', now_ms)
-- TTL 设为 2 * capacity / rate + 1 秒，防止数据永不过期
local ttl = math.floor(2 * capacity / rate) + 1
redis.call('EXPIRE', key, ttl)
return 1
"""


class RedisService:
    """Redis 业务逻辑服务，封装速率限制、会话缓存和通用 KV 操作。

    目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    # 重连间隔：秒。Redis 不可用时，下次调用操作间隔多久再尝试 ping。
    _RECONNECT_INTERVAL: int = 10

    def __init__(self, *, log_startup: bool = True) -> None:
        """初始化 RedisService。
        
        目的：初始化RedisService所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        settings = get_settings()
        self.client: Any | None = None
        masked_url = _mask_redis_url(settings.redis_url)
        try:
            # 使用二进制模式：decode_responses=False，由我们显式管理 UTF-8 编码
            # 这样能保证中文字符在不同平台/环境下的一致性
            self.client = Redis.from_url(
                settings.redis_url,
                decode_responses=False,  # 禁用隐式解码，由我们显式管理 UTF-8
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            self.client.ping()
            self._available = True
            self._last_connect_try: float | None = None
            if log_startup:
                logger.info("Redis 服务初始化成功: url=%s", masked_url)
        except (RedisConnectionError, Exception) as exc:
            self._available = False
            self._last_connect_try = time.time()
            if log_startup:
                logger.warning("Redis 不可用，所有缓存功能降级: url=%s, error=%s", masked_url, exc)

    @staticmethod
    def _encode_json(data: Any) -> bytes:
        """将 Python 对象序列化为 UTF-8 编码的 JSON 字节串。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        # ensure_ascii=False 保证中文直接写入，不再二次解码
        json_str = json.dumps(data, ensure_ascii=False)
        return json_str.encode(_REDIS_ENCODING)

    @staticmethod
    def _decode_json(data: bytes | str) -> Any:
        """将 Redis 返回的字节串/字符串反序列化为 Python 对象。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if isinstance(data, bytes):
            return json.loads(data.decode(_REDIS_ENCODING))
        return json.loads(data)

    def _try_reconnect(self) -> bool:
        """尝试验证 Redis 连接，必要时重建客户端。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        # 已有可用连接，无需重连
        if self._available and self.client is not None:
            return True

        # 退避检查：距上次重连尝试不足间隔时跳过，直接降级
        now = time.time()
        if self._last_connect_try is not None:
            elapsed = now - self._last_connect_try
            if elapsed < self._RECONNECT_INTERVAL:
                return False  # 仍在退避期内，快速放行

        # 记录本次重连尝试时间（无论成功失败都更新）
        self._last_connect_try = now

        # client 已被置 None 时，需要重建
        if self.client is None:
            try:
                settings = get_settings()
                self.client = Redis.from_url(
                    settings.redis_url,
                    decode_responses=False,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                )
            except Exception:
                self._available = False
                return False

        # ping 验证连接
        try:
            self.client.ping()
            self._available = True
            self._last_connect_try = None  # 重连成功后清除，重置退避周期
            logger.info("Redis 重连成功")
            return True
        except (RedisConnectionError, Exception) as exc:
            logger.debug("Redis 重连失败: %s", exc)
            self._available = False
            return False

    def check_rate_limit(
        self,
        key: str,
        *,
        rate: float = _DEFAULT_RATE,
        capacity: int = _DEFAULT_CAPACITY,
    ) -> bool:
        """令牌桶速率限制：通过 Redis + Lua 脚本实现原子性令牌桶算法。

        目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        # 参数校验前置：无论 Redis 是否可用，配置错误都必须拦截
        # 放在重连检查之前，避免 Redis 不可用时跳过校验导致"失败开放"
        if rate <= 0 or capacity < 1:
            logger.error(
                "令牌桶参数异常，触发限流: key=%s, rate=%s, capacity=%s",
                key,
                rate,
                capacity,
            )
            return False

        # 每次调用都尝试重连，解决"启动失败永久放行"问题
        if not self._try_reconnect():
            return True  # 仍不可用时降级放行，不阻塞业务

        rate_key = f"rate_limit:{key}".encode(_REDIS_ENCODING)

        try:
            # Lua 脚本：原子执行令牌桶逻辑
            # 内部通过 Redis TIME 获取服务端时间，保证多实例时钟一致
            # 参数：key, rate, capacity
            result = self.client.eval(  # type: ignore[union-attr]
                _TOKEN_BUCKET_SCRIPT,
                1,  # number of keys
                rate_key,
                rate,  # ARGV[1]: 每秒补充令牌数
                capacity,  # ARGV[2]: 桶容量
            )
            # Lua 返回值：1=成功，0=限流，-1=参数非法
            if result == 1:
                return True
            if result == -1:
                # Lua 侧也做了防御，但 Python 侧已校验，此分支理论上不会走到
                logger.error("Lua 脚本参数异常: key=%s", key)
                return False
            logger.warning(
                "令牌桶限流触发: key=%s, rate=%.3f, capacity=%d",
                key,
                rate,
                capacity,
            )
            return False
        except (RedisConnectionError, Exception) as exc:
            # Redis 断开：标记不可用，下次调用会触发重连
            self._available = False
            logger.warning("Redis 令牌桶执行异常，降级放行: %s", exc)
            return True

    def cache_session_context(
        self,
        session_id: str,
        context: dict[str, Any],
        *,
        ttl: int = 3600,
    ) -> bool:
        """缓存会话上下文信息。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if not self._available or self.client is None:
            return False

        try:
            cache_key = f"session_ctx:{session_id}".encode(_REDIS_ENCODING)
            # 使用 UTF-8 编码的 JSON 字节串写入，中文不再乱码
            self.client.setex(cache_key, ttl, self._encode_json(context))
            return True
        except (RedisConnectionError, Exception) as exc:
            logger.warning("会话上下文缓存写入失败: session=%s, error=%s", session_id, exc)
            return False

    def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        """读取缓存的会话上下文信息。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self._available or self.client is None:
            return None

        try:
            cache_key = f"session_ctx:{session_id}".encode(_REDIS_ENCODING)
            data = self.client.get(cache_key)
            if data is None:
                return None
            return self._decode_json(data)
        except (RedisConnectionError, Exception) as exc:
            logger.warning("会话上下文缓存读取失败: session=%s, error=%s", session_id, exc)
            return None

    def set(self, key: str, value: str, *, ttl: int | None = None) -> bool:
        """通用键值写入。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        if not self._available or self.client is None:
            return False

        try:
            key_bytes = key.encode(_REDIS_ENCODING)
            value_bytes = value.encode(_REDIS_ENCODING)
            if ttl:
                self.client.setex(key_bytes, ttl, value_bytes)
            else:
                self.client.set(key_bytes, value_bytes)
            return True
        except (RedisConnectionError, Exception) as exc:
            logger.warning("Redis SET 失败: key=%s, error=%s", key, exc)
            return False

    def get(self, key: str) -> str | None:
        """通用键值读取。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self._available or self.client is None:
            return None

        try:
            key_bytes = key.encode(_REDIS_ENCODING)
            data = self.client.get(key_bytes)
            if data is None:
                return None
            if isinstance(data, bytes):
                return data.decode(_REDIS_ENCODING)
            return data
        except (RedisConnectionError, Exception) as exc:
            logger.warning("Redis GET 失败: key=%s, error=%s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        """通用键值删除。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        if not self._available or self.client is None:
            return False

        try:
            key_bytes = key.encode(_REDIS_ENCODING)
            self.client.delete(key_bytes)
            return True
        except (RedisConnectionError, Exception) as exc:
            logger.warning("Redis DELETE 失败: key=%s, error=%s", key, exc)
            return False

    # ======================== 短期记忆（Redis List）======================= #
    # 数据结构：short_term:{session_id} → List[JSON bytes]
    # 操作语义：RPUSH 追加 + LRANGE 范围读取 + LTRIM 裁剪超长旧消息 + EXPIRE TTL 续期

    def append_message(
        self,
        session_id: str,
        message_data: dict[str, object],
        *,
        max_messages: int = 20,
        ttl: int = 1800,
    ) -> bool:
        """向会话短期记忆 List 追加一条消息，自动裁剪超长旧消息并续期 TTL。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        if not self._available or self.client is None:
            return False

        try:
            key_bytes = f"short_term:{session_id}".encode(_REDIS_ENCODING)
            json_bytes = self._encode_json(message_data)

            # 管道化执行：RPUSH → LTRIM → EXPIRE，减少网络往返
            pipe = self.client.pipeline()
            pipe.rpush(key_bytes, json_bytes)
            pipe.ltrim(key_bytes, -max_messages, -1)
            pipe.expire(key_bytes, ttl)
            pipe.execute()

            return True
        except (RedisConnectionError, Exception) as exc:
            logger.warning(
                "Redis 追加消息失败: session=%s, error=%s",
                session_id,
                exc,
            )
            return False

    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """读取会话短期记忆最近若干条消息。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self._available or self.client is None:
            return []

        try:
            key_bytes = f"short_term:{session_id}".encode(_REDIS_ENCODING)
            # LRANGE -limit -1 取最后 limit 条，Redis List 按 RPUSH 顺序存储，
            # 因此 -limit 到 -1 已经是时间正序（从旧到新），直接返回无需反转
            raw_items = self.client.lrange(key_bytes, -limit, -1)
            if raw_items is None:
                return []

            results: list[dict[str, object]] = []
            for raw in raw_items:
                if isinstance(raw, bytes):
                    item = self._decode_json(raw)
                elif isinstance(raw, str):
                    item = self._decode_json(raw)
                else:
                    item = raw
                if isinstance(item, dict):
                    results.append(item)

            return results
        except (RedisConnectionError, Exception) as exc:
            logger.warning(
                "Redis 读取最近消息失败: session=%s, error=%s",
                session_id,
                exc,
            )
            return []

    def get_all_messages(
        self,
        session_id: str,
    ) -> list[dict[str, object]]:
        """读取会话短期记忆全部消息。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self._available or self.client is None:
            return []

        try:
            key_bytes = f"short_term:{session_id}".encode(_REDIS_ENCODING)
            raw_items = self.client.lrange(key_bytes, 0, -1)
            if raw_items is None:
                return []

            results: list[dict[str, object]] = []
            for raw in raw_items:
                if isinstance(raw, bytes):
                    item = self._decode_json(raw)
                elif isinstance(raw, str):
                    item = self._decode_json(raw)
                else:
                    item = raw
                if isinstance(item, dict):
                    results.append(item)

            return results
        except (RedisConnectionError, Exception) as exc:
            logger.warning(
                "Redis 读取全部消息失败: session=%s, error=%s",
                session_id,
                exc,
            )
            return []

    def delete_session(self, session_id: str) -> bool:
        """删除会话短期记忆。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        if not self._available or self.client is None:
            return False

        try:
            key_bytes = f"short_term:{session_id}".encode(_REDIS_ENCODING)
            self.client.delete(key_bytes)
            return True
        except (RedisConnectionError, Exception) as exc:
            logger.warning(
                "Redis 删除会话失败: session=%s, error=%s",
                session_id,
                exc,
            )
            return False

    def get_ttl(self, session_id: str) -> int:
        """获取会话短期记忆剩余 TTL。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self._available or self.client is None:
            return -2

        try:
            key_bytes = f"short_term:{session_id}".encode(_REDIS_ENCODING)
            return self.client.ttl(key_bytes)
        except (RedisConnectionError, Exception) as exc:
            logger.warning(
                "Redis 获取 TTL 失败: session=%s, error=%s",
                session_id,
                exc,
            )
            return -2
