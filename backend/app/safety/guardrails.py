class SafetyGuard:
    """把输入和输出治理独立出来，后续方便接审核规则和模型判别器。"""

    HIGH_RISK_KEYWORDS = ("不想活了", "自杀", "伤害自己")

    def inspect_input(self, message: str) -> str:
        if any(keyword in message for keyword in self.HIGH_RISK_KEYWORDS):
            return "high"
        return "low"

    def inspect_output(self, reply: str, safety_level: str) -> str:
        if safety_level == "high":
            return (
                f"{reply} 如果你存在现实中的安全风险，请尽快联系身边可信的人，"
                "或立刻联系当地紧急援助资源。"
            )
        return reply
