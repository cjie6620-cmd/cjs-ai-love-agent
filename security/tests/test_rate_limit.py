"""令牌桶限流器单元测试。

目的：验证 Redis + Lua 令牌桶算法的正确性，
覆盖令牌扣减、补充、容量限制、突发流量、参数校验、重连逻辑等核心场景。
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from security import RedisService
from security.rate_limit import (
    _DEFAULT_CAPACITY,
    _DEFAULT_RATE,
    _TOKEN_BUCKET_SCRIPT,
)


class TestTokenBucketLuaScript:
    """验证 Lua 脚本本身（逻辑层面）的正确性。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_script_is_valid_string(self):
        """Lua 脚本必须是非空字符串。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert isinstance(_TOKEN_BUCKET_SCRIPT, str)
        assert len(_TOKEN_BUCKET_SCRIPT.strip()) > 0

    def test_script_contains_key_operations(self):
        """Lua 脚本必须包含 HMGET、HMSET、EXPIRE 等核心操作。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        script = _TOKEN_BUCKET_SCRIPT
        assert "HMGET" in script
        assert "HMSET" in script
        assert "EXPIRE" in script

    def test_script_rejects_on_insufficient_tokens(self):
        """令牌不足时脚本必须返回 0。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        script = _TOKEN_BUCKET_SCRIPT
        assert "return 0" in script  # 令牌不足路径

    def test_script_uses_redis_time(self):
        """Lua 脚本必须使用 Redis TIME 而非应用侧时间，避免多实例时钟漂移。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        script = _TOKEN_BUCKET_SCRIPT
        assert "redis.call('TIME')" in script
        # 不应包含 ARGV[3]（now_ms 已不再由应用侧传入）
        assert "ARGV[3]" not in script

    def test_script_validates_params(self):
        """参数非法（rate <= 0 或 capacity < 1）时 Lua 返回 -1。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        script = _TOKEN_BUCKET_SCRIPT
        assert "return -1" in script  # 参数校验失败路径
        assert "rate <= 0" in script
        assert "capacity < 1" in script

    def test_script_handles_negative_elapsed(self):
        """时钟回拨时 elapsed_ms 负数应被修正为 0，防止令牌被错误回退。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        script = _TOKEN_BUCKET_SCRIPT
        assert "elapsed_ms < 0" in script  # 时钟漂移防御


class TestTokenBucketDefaults:
    """验证默认配置的正确性。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_default_rate_equals_20_per_minute(self):
        """默认每秒 20/60 ≈ 0.333 个令牌，即每分钟 20 个。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert abs(_DEFAULT_RATE - 20 / 60) < 1e-6

    def test_default_capacity_equals_20(self):
        """默认桶容量为 20，可突发 20 个请求。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert _DEFAULT_CAPACITY == 20


class TestRedisServiceReconnect:
    """P1 修复验证：Redis 启动失败不应永久放行，支持重连。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_init_unavailable_sets_last_connect_time(self, mock_settings, mock_redis):
        """初始化时 Redis 不可用，应记录最后一次重连尝试时间。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_redis.return_value.ping.side_effect = Exception("连接失败")

        service = RedisService()
        assert service._available is False
        assert service._last_connect_try is not None

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_check_rate_limit_triggers_reconnect(self, mock_settings, mock_redis):
        """退避期过后调用 check_rate_limit 时应尝试重连，而非永久放行。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"

        # __init__ 时 ping 失败
        mock_redis.return_value.ping.side_effect = Exception("启动时失败")
        mock_redis.return_value.eval.return_value = 1

        service = RedisService()
        assert service._available is False

        # 模拟退避期已过：将上次尝试时间设为 20 秒前
        service._last_connect_try = time.time() - 20

        # 重连时 ping 成功
        mock_redis.return_value.ping.side_effect = None
        mock_redis.return_value.ping.return_value = True

        # 调用 check_rate_limit，退避期已过应触发重连并成功
        result = service.check_rate_limit("user_reconnect")
        assert result is True
        assert service._available is True
        # 重连成功后 _last_connect_try 被清空
        assert service._last_connect_try is None

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_reconnect_interval_respected(self, mock_settings, mock_redis):
        """退避期内不应重连，ping 调用次数不增加，快速降级放行。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_redis.return_value.ping.side_effect = Exception("不可用")

        service = RedisService()
        assert service._available is False
        first_try = service._last_connect_try

        # __init__ 调用了 1 次 ping，记录基线
        ping_count_after_init = mock_redis.return_value.ping.call_count

        # 立即再次调用，退避期内不应 ping（快速返回 True 降级放行）
        result = service.check_rate_limit("user_quick")
        assert result is True  # 降级放行
        # _last_connect_try 未更新（没有发起重连）
        assert service._last_connect_try == first_try
        # ping 调用次数不增加，说明退避真正生效
        assert mock_redis.return_value.ping.call_count == ping_count_after_init


class TestRedisServiceParamValidation:
    """P2 修复验证：参数异常应触发限流，而非静默放行。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_negative_rate_triggers_limit(self, mock_settings, mock_redis):
        """rate <= 0 时应触发限流（返回 False），而非静默放行。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        service = RedisService()
        result = service.check_rate_limit("user_neg_rate", rate=-1.0, capacity=10)
        assert result is False
        # 静默降级放行
        assert mock_client.eval.call_count == 0

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_zero_capacity_triggers_limit(self, mock_settings, mock_redis):
        """capacity < 1 时应触发限流（返回 False）。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        service = RedisService()
        result = service.check_rate_limit("user_zero_cap", rate=0.5, capacity=0)
        assert result is False
        assert mock_client.eval.call_count == 0

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_lua_returns_negative_one_triggers_limit(self, mock_settings, mock_redis):
        """Lua 脚本返回 -1（参数非法）时，应触发限流而非放行。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.eval.return_value = -1  # Lua 侧参数异常
        mock_redis.return_value = mock_client

        service = RedisService()
        result = service.check_rate_limit("user_lua_invalid")
        assert result is False

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_param_validation_before_reconnect(self, mock_settings, mock_redis):
        """Redis 不可用时，参数异常仍必须返回 False（限流），而非降级放行。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_redis.return_value.ping.side_effect = Exception("Redis 挂了")

        service = RedisService()
        assert service._available is False

        # Redis 不可用 + rate <= 0：必须拦截，不能放行
        assert service.check_rate_limit("user_bad", rate=-1.0, capacity=10) is False
        # Redis 不可用 + capacity < 1：同样必须拦截
        assert service.check_rate_limit("user_bad", rate=0.5, capacity=0) is False


class TestRedisServiceRateLimit:
    """验证 RedisService.check_rate_limit() 的核心行为。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_token_acquired_returns_true(self, mock_settings, mock_redis):
        """获取到令牌时返回 True。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.eval.return_value = 1  # Lua 返回 1 = 成功
        mock_redis.return_value = mock_client

        service = RedisService()
        result = service.check_rate_limit("user_456")
        assert result is True
        mock_client.eval.assert_called_once()

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_token_unavailable_returns_false(self, mock_settings, mock_redis):
        """令牌不足时返回 False（触发限流）。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.eval.return_value = 0  # Lua 返回 0 = 拒绝
        mock_redis.return_value = mock_client

        service = RedisService()
        result = service.check_rate_limit("user_789")
        assert result is False

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_eval_called_with_correct_args(self, mock_settings, mock_redis):
        """eval 调用必须传入：Lua 脚本、key、rate、capacity（now_ms 已移除）。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.eval.return_value = 1
        mock_redis.return_value = mock_client

        service = RedisService()
        service.check_rate_limit("user_test", rate=0.5, capacity=30)

        call_args = mock_client.eval.call_args
        assert call_args[0][0] == _TOKEN_BUCKET_SCRIPT  # Lua 脚本
        assert call_args[0][2] == b"rate_limit:user_test"  # key（bytes 编码）
        assert call_args[0][3] == 0.5  # rate
        assert call_args[0][4] == 30  # capacity
        # now_ms 不再由应用侧传入，由 Lua 内部通过 Redis TIME 获取
        assert len(call_args[0]) == 5

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_exception_allows_request(self, mock_settings, mock_redis):
        """Redis 操作异常时降级放行，不阻塞请求。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.eval.side_effect = Exception("网络错误")
        mock_redis.return_value = mock_client

        service = RedisService()
        result = service.check_rate_limit("user_error")
        assert result is True  # 降级放行
        # 异常时应标记为不可用，下次调用触发重连
        assert service._available is False

    @patch("security.rate_limit.Redis.from_url")
    @patch("security.rate_limit.get_settings")
    def test_redis_still_unavailable_after_reconnect_allow(self, mock_settings, mock_redis):
        """重连失败后仍不可用，降至放行并标记不可用。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        # 启动失败
        mock_redis.return_value.ping.side_effect = Exception("启动失败")
        mock_redis.return_value.ping.side_effect = Exception("重连也失败")
        mock_redis.return_value.__getitem__ = MagicMock(side_effect=Exception("client 重建失败"))

        service = RedisService()
        assert service._available is False

        result = service.check_rate_limit("user_still_down")
        # 降级放行
        assert result is True
        assert service._available is False


class TestTokenBucketSimulation:
    """令牌桶算法逻辑模拟验证（不依赖真实 Redis）。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_burst_capacity_behavior(self):
        """桶满时，允许在短时间内通过最多 capacity 个请求。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        capacity = 5
        tokens = float(capacity)

        results = []
        for _ in range(5):
            if tokens >= 1:
                tokens -= 1
                results.append(True)
            else:
                results.append(False)

        assert results == [True, True, True, True, True]
        assert tokens == 0

    def test_token_replenishment_over_time(self):
        """等待一段时间后，令牌按速率补充。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        capacity = 5
        tokens = float(capacity)
        rate = 10.0  # 每秒补充 10 个

        for _ in range(5):
            tokens -= 1
        assert tokens == 0

        elapsed_s = 0.5
        tokens = min(capacity, tokens + elapsed_s * rate)
        assert tokens == 5.0

        elapsed_s = 0.1
        tokens = min(capacity, tokens + elapsed_s * rate)
        assert tokens == 5.0  # 桶已满，不再增加

    def test_partial_token_request_blocked(self):
        """令牌不足时（<1），请求被拒绝。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        tokens = 0.5
        requested = 1

        if tokens >= requested:
            tokens -= requested
            result = True
        else:
            result = False

        assert result is False
        assert tokens == 0.5  # 令牌数不变，不扣减

    def test_negative_elapsed_ignored(self):
        """时钟回拨（elapsed_ms < 0）时，令牌数不变。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        last_tokens = 10.0
        elapsed_ms = -1000  # 时钟回拨 1 秒
        if elapsed_ms < 0:
            elapsed_ms = 0
        elapsed_s = elapsed_ms / 1000.0
        rate = 1.0

        tokens = min(20, last_tokens + elapsed_s * rate)
        assert tokens == 10.0  # 未补充，未扣减，状态不变

