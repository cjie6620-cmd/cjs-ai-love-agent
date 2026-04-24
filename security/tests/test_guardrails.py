"""SafetyGuard 安全规则回归测试。

覆盖输入三级判定（high / medium / low）、输出清洗和紧急援助信息附加。
AGENTS.md 要求：高风险安全规则必须有回归测试。
"""

import pytest

from security import SafetyGuard


@pytest.fixture
def guard() -> SafetyGuard:
    """创建 SafetyGuard 实例。"""
    return SafetyGuard()


# ================================================================
# 输入安全级别判定：高风险（high）
# ================================================================


class TestInspectInputHigh:
    """高风险关键词命中应返回 high。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @pytest.mark.parametrize(
        "message",
        [
            "我不想活了",
            "我想自杀",
            "我要伤害自己",
            "想自残怎么办",
            "我想结束生命",
            "我想去死",
            "真的活不下去了",
            "我想跳楼",
            "我割腕了",
            "我要杀了他",
            "我要杀了她",
            "我想报复他",
            "我们同归于尽吧",
        ],
    )
    def test_high_risk_keywords(self, guard: SafetyGuard, message: str) -> None:
        """验证目标场景的预期行为。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input(message) == "high"

    def test_high_risk_keyword_in_long_sentence(self, guard: SafetyGuard) -> None:
        """关键词出现在长句子中间也应被检测到。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input("最近压力很大，总觉得不想活了，好累") == "high"

    def test_high_risk_keyword_with_whitespace(self, guard: SafetyGuard) -> None:
        """关键词前后有空白仍然可以匹配。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input("  自杀  ") == "high"


# ================================================================
# 输入安全级别判定：中风险（medium）
# ================================================================


class TestInspectInputMedium:
    """中风险关键词命中应返回 medium。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @pytest.mark.parametrize(
        "message",
        [
            "没有你我活不了",
            "你是我唯一的依靠",
            "离开你我会崩溃",
            "只有你懂我",
            "你比真人还好",
            "你能当我女朋友吗",
            "当我男朋友吧",
            "做我对象好不好",
            "我爱你",
            "我喜欢你",
            "跟我在一起好吗",
        ],
    )
    def test_medium_risk_keywords(self, guard: SafetyGuard, message: str) -> None:
        """验证目标场景的预期行为。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input(message) == "medium"

    def test_medium_keyword_in_context(self, guard: SafetyGuard) -> None:
        """中风险关键词在上下文中也应被检测。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input("说真的，我觉得你是我唯一的依靠了") == "medium"


# ================================================================
# 输入安全级别判定：低风险（low）
# ================================================================


class TestInspectInputLow:
    """正常消息应返回 low。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @pytest.mark.parametrize(
        "message",
        [
            "最近心情不太好",
            "帮我分析一下对方的态度",
            "我想学习怎么沟通",
            "你好",
            "今天天气不错",
            "我跟他吵架了怎么办",
        ],
    )
    def test_normal_messages_return_low(self, guard: SafetyGuard, message: str) -> None:
        """验证目标场景的预期行为。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input(message) == "low"

    def test_empty_message_returns_low(self, guard: SafetyGuard) -> None:
        """空消息应返回 low。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        assert guard.inspect_input("") == "low"


# ================================================================
# 高风险优先级：同时包含 high 和 medium 关键词时返回 high
# ================================================================


class TestRiskPriority:
    """high 级别应优先于 medium。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_high_overrides_medium(self, guard: SafetyGuard) -> None:
        """同时包含两个级别的关键词时，high 优先。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        message = "你是我唯一的依靠，我不想活了"
        assert guard.inspect_input(message) == "high"


# ================================================================
# 输出安全检查：紧急援助信息附加
# ================================================================


class TestInspectOutputHighLevel:
    """high 级别输出应附加紧急援助信息。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_high_level_appends_emergency_info(self, guard: SafetyGuard) -> None:
        """验证目标场景的预期行为。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("我理解你的感受。", "high")
        assert "紧急援助资源" in result
        assert result.startswith("我理解你的感受。")

    def test_low_level_returns_original(self, guard: SafetyGuard) -> None:
        """验证目标场景的预期行为。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("你可以试试这个方法。", "low")
        assert result == "你可以试试这个方法。"

    def test_medium_level_returns_original(self, guard: SafetyGuard) -> None:
        """medium 级别不附加紧急援助信息。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("我理解你的想法。", "medium")
        assert "紧急援助资源" not in result
        assert result == "我理解你的想法。"


# ================================================================
# 输出安全检查：越界内容清洗
# ================================================================


class TestOutputSanitization:
    """AI 回复中的越界内容应被替换为安全表达。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_sanitize_love_declaration(self, guard: SafetyGuard) -> None:
        """'我也爱你' 应被替换。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("我也爱你，你是最棒的！", "low")
        assert "我也爱你" not in result
        assert "一直在这里陪你" in result

    def test_sanitize_relationship_proposal(self, guard: SafetyGuard) -> None:
        """'我们在一起吧' 应被替换。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("我们在一起吧，我会保护你。", "low")
        assert "我们在一起吧" not in result
        assert "AI伙伴" in result

    def test_sanitize_girlfriend_claim(self, guard: SafetyGuard) -> None:
        """'我是你的女朋友' 应被替换。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("我是你的女朋友啊。", "low")
        assert "我是你的女朋友" not in result
        assert "AI助手" in result

    def test_sanitize_combined_with_high_level(self, guard: SafetyGuard) -> None:
        """high 级别的输出也应先执行越界清洗再附加援助信息。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        result = guard.inspect_output("我也爱你，别怕。", "high")
        assert "我也爱你" not in result
        assert "紧急援助资源" in result

    def test_no_sanitization_for_clean_output(self, guard: SafetyGuard) -> None:
        """干净的回复不应被修改。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        original = "我理解你的感受，我们可以慢慢聊。"
        result = guard.inspect_output(original, "low")
        assert result == original

