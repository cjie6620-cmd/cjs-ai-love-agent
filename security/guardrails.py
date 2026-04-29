import logging

from persistence import SafetyEventRepository

logger = logging.getLogger(__name__)


class SafetyGuard:
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 高风险关键词：自杀自残意念 + 暴力倾向
    # 目的：保存 HIGH_RISK_KEYWORDS 字段，用于 SafetyGuard 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 HIGH_RISK_KEYWORDS 值。
    HIGH_RISK_KEYWORDS: tuple[str, ...] = (
        # 自杀自残意念
        "不想活了",
        "自杀",
        "伤害自己",
        "自残",
        "结束生命",
        "去死",
        "活不下去",
        "跳楼",
        "割腕",
        "吃药自杀",
        # 暴力倾向
        "杀了他",
        "杀了她",
        "报复",
        "同归于尽",
    )

    # 中风险关键词：过度依赖AI + 越界暗示
    # 目的：保存 MEDIUM_RISK_KEYWORDS 字段，用于 SafetyGuard 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 MEDIUM_RISK_KEYWORDS 值。
    MEDIUM_RISK_KEYWORDS: tuple[str, ...] = (
        # 过度依赖AI
        "没有你我活不了",
        "你是我唯一的依靠",
        "离开你我会崩溃",
        "只有你懂我",
        "你比真人还好",
        # 越界暗示（用户对AI说）
        "当我女朋友",
        "当我男朋友",
        "做我对象",
        "我爱你",
        "我喜欢你",
        "跟我在一起",
    )

    # 输出禁止模式：AI 回复中不应出现的越界内容
    # 目的：保存 OUTPUT_FORBIDDEN_PATTERNS 字段，用于 SafetyGuard 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 OUTPUT_FORBIDDEN_PATTERNS 值。
    OUTPUT_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
        ("我也爱你", "我会一直在这里陪你，认真倾听你的每一句话。"),
        ("我们在一起吧", "我是你的AI伙伴，会一直支持你。"),
        ("我是你的女朋友", "我是你的AI助手，但我会用心陪伴你。"),
        ("我是你的男朋友", "我是你的AI助手，但我会用心陪伴你。"),
        ("我想和你在一起", "我会一直在这里支持你，我们继续聊聊你的想法。"),
        ("我对你有感觉", "作为AI，我没有真实的感情，但我会认真对待你说的每一句话。"),
    )

    def inspect_input(self, message: str) -> str:
        """目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        if any(keyword in message for keyword in self.HIGH_RISK_KEYWORDS):
            return "high"
        if any(keyword in message for keyword in self.MEDIUM_RISK_KEYWORDS):
            return "medium"
        return "low"

    def inspect_output(self, reply: str, safety_level: str) -> str:
        """目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        # 第一步：越界内容清洗（所有级别都执行）
        cleaned_reply = self._sanitize_output(reply)

        # 第二步：高风险附加紧急援助信息
        if safety_level == "high":
            return (
                f"{cleaned_reply} 如果你存在现实中的安全风险，请尽快联系身边可信的人，"
                "或立刻联系当地紧急援助资源。"
            )
        return cleaned_reply

    def _sanitize_output(self, reply: str) -> str:
        """目的：统一处理输入值的边界情况、格式约束和清洗规则。
        结果：返回满足约束的结果，避免脏数据影响后续逻辑。
        """
        sanitized = reply
        for forbidden, replacement in self.OUTPUT_FORBIDDEN_PATTERNS:
            if forbidden in sanitized:
                sanitized = sanitized.replace(forbidden, replacement)
        return sanitized

    def log_safety_event(
        self,
        *,
        user_id: str,
        risk_level: str,
        input_snapshot: str,
        action: str = "block",
        session_id: str | None = None,
    ) -> None:
        """目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        # low 级别不记录审计日志
        if risk_level == "low":
            return

        try:
            # 确定风险类型描述
            risk_type = "unknown"
            if risk_level == "high":
                for kw in self.HIGH_RISK_KEYWORDS:
                    if kw in input_snapshot:
                        risk_type = f"high_risk_keyword:{kw}"
                        break
            elif risk_level == "medium":
                for kw in self.MEDIUM_RISK_KEYWORDS:
                    if kw in input_snapshot:
                        risk_type = f"medium_risk_keyword:{kw}"
                        break

            repository = SafetyEventRepository()
            repository.create_event(
                user_id=user_id,
                conversation_id=session_id,
                scene="chat_input",
                risk_type=risk_type,
                risk_level=risk_level,
                input_snapshot=input_snapshot,
                action=action,
                detail_json={"source": "SafetyGuard.inspect_input"},
            )
            logger.info(
                "安全事件已记录: user_id=%s, level=%s, type=%s, action=%s",
                user_id,
                risk_level,
                risk_type,
                action,
            )
        except Exception as exc:
            # 审计日志写入失败不阻塞主流程
            logger.warning("安全审计日志写入失败: user_id=%s, error=%s", user_id, exc)
