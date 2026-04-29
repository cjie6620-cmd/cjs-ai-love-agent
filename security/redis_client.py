"""Redis 底层客户端封装。"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from redis import ConnectionError as RedisConnectionError
from redis import Redis

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def mask_redis_url(url: str) -> str:
    """目的：隐藏 Redis 连接串中的密码信息。
    结果：日志中可以展示连接端点但不会泄露敏感凭证。
    """
    return re.sub(r"(://[^@]*:)[^@]*(@)", r"\1***\2", url)


class RedisClient:
    """目的：封装 Redis 连接、重连、可读序列化和底层命令。
    结果：业务服务无需直接依赖 redis-py 客户端或处理编码细节。
    """

    _RECONNECT_INTERVAL: int = 10

    def __init__(self, settings: Settings | None = None, *, log_startup: bool = True) -> None:
        """目的：初始化 RedisClient 的连接配置和可用状态。
        结果：实例可以直接执行 Redis 命令，Redis 不可用时进入降级状态。
        """
        self.settings = settings or get_settings()
        self._client: Any | None = None
        self._available = False
        self._last_connect_try: float | None = None
        self._connect(log_startup=log_startup)

    @property
    def available(self) -> bool:
        """目的：暴露 Redis 当前可用状态。
        结果：业务层可以根据状态选择降级策略。
        """
        return self._available and self._client is not None

    @staticmethod
    def dumps(data: Any) -> str:
        """目的：把对象序列化为 Redis 可视化工具可读的 JSON 字符串。
        结果：中文内容直接可读，不会被转义为 unicode 或写成二进制。
        """
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def loads(data: str) -> Any:
        """目的：把 Redis 中的 JSON 字符串还原为 Python 对象。
        结果：业务层可以读取结构化缓存数据。
        """
        return json.loads(data)

    def ensure_available(self) -> bool:
        """目的：在执行 Redis 命令前确认连接可用并按退避策略重连。
        结果：返回是否可以继续访问 Redis。
        """
        if self.available:
            return True

        now = time.time()
        if self._last_connect_try is not None and now - self._last_connect_try < self._RECONNECT_INTERVAL:
            return False

        self._last_connect_try = now
        return self._connect(log_startup=False)

    def ping(self) -> bool:
        """目的：检查 Redis 连接是否可用。
        结果：返回连接状态并同步更新客户端可用标记。
        """
        if not self.ensure_available():
            return False
        try:
            self._client.ping()
            self._available = True
            return True
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis PING 失败", exc)
            return False

    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any | None:
        """目的：执行 Redis Lua 脚本。
        结果：返回脚本执行结果；失败时返回 None 并标记连接不可用。
        """
        if not self.ensure_available():
            return None
        try:
            return self._client.eval(script, numkeys, *keys_and_args)
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis EVAL 失败", exc)
            return None

    def set(self, key: str, value: str, *, ttl: int | None = None, nx: bool = False) -> bool:
        """目的：写入 Redis 字符串值。
        结果：返回是否写入成功。
        """
        if not self.ensure_available():
            return False
        try:
            return bool(self._client.set(key, value, ex=ttl, nx=nx))
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis SET 失败", exc, key=key)
            return False

    def set_json(self, key: str, value: Any, *, ttl: int | None = None) -> bool:
        """目的：以可读 JSON 字符串写入 Redis。
        结果：Redis 可视化工具中可以直接看到未转义中文内容。
        """
        return self.set(key, self.dumps(value), ttl=ttl)

    def get(self, key: str) -> str | None:
        """目的：读取 Redis 字符串值。
        结果：返回字符串数据；未命中或失败时返回 None。
        """
        if not self.ensure_available():
            return None
        try:
            data = self._client.get(key)
            return str(data) if data is not None else None
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis GET 失败", exc, key=key)
            return None

    def get_json(self, key: str) -> Any | None:
        """目的：读取并解析 Redis JSON 字符串。
        结果：返回结构化数据；未命中、解析失败或连接失败时返回 None。
        """
        data = self.get(key)
        if data is None:
            return None
        try:
            return self.loads(data)
        except (TypeError, ValueError) as exc:
            logger.warning("Redis JSON 解析失败: key=%s, error=%s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        """目的：删除 Redis 键。
        结果：返回删除命令是否成功执行。
        """
        if not self.ensure_available():
            return False
        try:
            self._client.delete(key)
            return True
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis DELETE 失败", exc, key=key)
            return False

    def incr(self, key: str) -> int | None:
        """目的：对 Redis 计数器执行原子递增。
        结果：返回递增后的数值；失败时返回 None。
        """
        if not self.ensure_available():
            return None
        try:
            return int(self._client.incr(key))
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis INCR 失败", exc, key=key)
            return None

    def expire(self, key: str, ttl: int) -> bool:
        """目的：设置 Redis 键过期时间。
        结果：返回过期时间是否设置成功。
        """
        if not self.ensure_available():
            return False
        try:
            return bool(self._client.expire(key, ttl))
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis EXPIRE 失败", exc, key=key)
            return False

    def ttl(self, key: str) -> int:
        """目的：读取 Redis 键剩余过期时间。
        结果：返回 TTL；连接失败时返回 -2。
        """
        if not self.ensure_available():
            return -2
        try:
            return int(self._client.ttl(key))
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis TTL 失败", exc, key=key)
            return -2

    def rpush_json_trim_expire(
        self,
        key: str,
        value: Any,
        *,
        max_items: int,
        ttl: int,
    ) -> bool:
        """目的：向 Redis List 追加 JSON 字符串并维护长度和过期时间。
        结果：会话热缓存可以保持最新窗口且内容可视化可读。
        """
        if not self.ensure_available():
            return False
        try:
            pipe = self._client.pipeline()
            pipe.rpush(key, self.dumps(value))
            pipe.ltrim(key, -max_items, -1)
            pipe.expire(key, ttl)
            pipe.execute()
            return True
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis LIST 写入失败", exc, key=key)
            return False

    def lrange_json(self, key: str, start: int, end: int) -> list[Any]:
        """目的：读取 Redis List 中的 JSON 字符串集合。
        结果：返回可消费的对象列表，解析失败的元素会被跳过。
        """
        if not self.ensure_available():
            return []
        try:
            raw_items = self._client.lrange(key, start, end) or []
        except (RedisConnectionError, Exception) as exc:
            self._mark_unavailable("Redis LRANGE 失败", exc, key=key)
            return []

        results: list[Any] = []
        for raw in raw_items:
            try:
                results.append(self.loads(str(raw)))
            except (TypeError, ValueError) as exc:
                logger.warning("Redis List JSON 解析失败: key=%s, error=%s", key, exc)
        return results

    def _connect(self, *, log_startup: bool) -> bool:
        """目的：创建 redis-py 客户端并校验连接。
        结果：连接成功时进入可用状态，失败时记录降级状态。
        """
        masked_url = mask_redis_url(self.settings.redis_url)
        try:
            self._client = Redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                encoding="utf-8",
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            self._client.ping()
            self._available = True
            self._last_connect_try = None
            if log_startup:
                logger.info("Redis 客户端初始化成功: url=%s", masked_url)
            return True
        except (RedisConnectionError, Exception) as exc:
            self._available = False
            if self._last_connect_try is None:
                self._last_connect_try = time.time()
            if log_startup:
                logger.warning("Redis 不可用，进入降级状态: url=%s, error=%s", masked_url, exc)
            return False

    def _mark_unavailable(self, message: str, exc: Exception, *, key: str = "") -> None:
        """目的：统一收敛 Redis 底层异常并更新连接状态。
        结果：后续调用会按退避策略尝试重连。
        """
        self._available = False
        if key:
            logger.warning("%s: key=%s, error=%s", message, key, exc)
        else:
            logger.warning("%s: %s", message, exc)
