"""
QQ 邮箱发送工具模块。

提供企业级的邮件发送功能，支持普通文本邮件和 HTML 格式邮件。
默认处于禁用状态，需要正确配置发件人邮箱和授权码后方可启用。

环境变量配置（推荐）：
- QQ_EMAIL: 发件人 QQ 邮箱地址
- QQ_EMAIL_PASSWORD: QQ 邮箱授权码

QQ邮箱SMTP配置说明：
- 服务器地址：smtp.qq.com
- 端口：465（使用 SSL 加密）
- 授权码：需在 QQ 邮箱设置中生成，非 QQ 密码
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from .base import BaseTool, ToolResult

# 配置模块级日志记录器
logger = logging.getLogger(__name__)

# 环境变量键名常量
_ENV_EMAIL = "QQ_EMAIL"
_ENV_PASSWORD = "QQ_EMAIL_PASSWORD"


class EmailTool(BaseTool):
    """目的：封装QQ 邮箱发送工具类相关工具能力并对外暴露统一入口。
    结果：业务层可按一致方式判断或调用该能力。
    """

    # 目的：保存 name 字段，用于 EmailTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name = "email"
    # 目的：保存 description 字段，用于 EmailTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description = "邮件发送工具"

    # QQ 邮箱 SMTP 服务器配置
    # 目的：保存 SMTP_SERVER 字段，用于 EmailTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 SMTP_SERVER 值。
    SMTP_SERVER: str = "smtp.qq.com"
    # 目的：保存 SMTP_PORT 字段，用于 EmailTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 SMTP_PORT 值。
    SMTP_PORT: int = 465

    def __init__(
        self,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
    ) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        # 优先使用传入参数，否则从环境变量读取
        self.sender_email: str | None = sender_email or os.environ.get(_ENV_EMAIL)
        self.sender_password: str | None = sender_password or os.environ.get(_ENV_PASSWORD)

        # 当最终邮箱配置齐备时启用工具
        self.enabled = bool(self.sender_email and self.sender_password)

        if self.enabled:
            logger.info(
                "邮件工具已启用，发件人: %s, SMTP服务器: %s:%d",
                self.sender_email,
                self.SMTP_SERVER,
                self.SMTP_PORT,
            )
        else:
            logger.warning(
                "邮件工具未启用，请提供有效的发件人邮箱和授权码"
            )

    def is_enabled(self) -> bool:
        """目的：根据发件邮箱和授权码配置判断 SMTP 能力是否可用。
        结果：返回 True 表示可以尝试发送邮件。
        """
        return self.enabled

    def disabled_message(self) -> str:
        """目的：在邮箱配置缺失时提供明确的禁用原因。
        结果：返回可展示给上层的错误说明。
        """
        return "邮件工具未启用，请检查发件人邮箱和授权码配置"

    def invoke(self, **kwargs: Any) -> ToolResult:
        """目的：兼容 Agent 工具编排，统一收敛邮件发送输入与返回结构。
        结果：上层无需关心具体发送方法，只需通过 invoke 调用。
        """
        to_emails = kwargs.get("to_emails")
        subject = kwargs.get("subject")
        body = kwargs.get("body")
        html = kwargs.get("html")
        return super().invoke(
            to_emails=to_emails,
            subject=subject,
            body=body,
            html=html,
        )

    def _invoke(
        self,
        **kwargs: Any,
    ) -> ToolResult:
        """目的：封装实际 SMTP 发送逻辑，并输出统一结果。
        结果：返回标准化工具结果，便于 Agent 和业务层直接消费。
        """
        to_emails = self._normalize_recipients(kwargs.get("to_emails"))
        subject = self._required_text(kwargs.get("subject"), "邮件主题")
        body = self._required_text(kwargs.get("body"), "邮件正文")
        html = self._optional_text(kwargs.get("html"))
        return self.send(
            to_emails=to_emails,
            subject=subject,
            body=body,
            html=html,
        )

    def send(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
        html: Optional[str] = None,
    ) -> ToolResult:
        """目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        # 空值判断：检查工具是否启用
        if not self.enabled:
            error_msg = self.disabled_message()
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # 空值判断：检查收件人列表
        if not to_emails:
            error_msg = "收件人列表不能为空"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 空值判断：检查邮件主题
        if not subject or not subject.strip():
            error_msg = "邮件主题不能为空"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 空值判断：检查发件人邮箱
        if not self.sender_email:
            error_msg = "发件人邮箱未配置"
            logger.error(error_msg)
            raise ValueError(error_msg)
        if not self.sender_password:
            error_msg = "发件人授权码未配置"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            "开始发送邮件: 主题='%s', 收件人=%s, 发件人=%s",
            subject,
            to_emails,
            self.sender_email,
        )

        try:
            # 创建邮件对象
            message = MIMEMultipart("alternative")
            message["From"] = self.sender_email
            message["To"] = ", ".join(to_emails)
            message["Subject"] = subject.strip()

            # 附加纯文本正文
            if body:
                message.attach(MIMEText(body, "plain", "utf-8"))

            # 附加 HTML 正文（如果提供）
            if html:
                message.attach(MIMEText(html, "html", "utf-8"))

            # 建立 SSL 安全连接并发送邮件
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                self.SMTP_SERVER,
                self.SMTP_PORT,
                context=context,
            ) as server:
                # 使用授权码登录
                server.login(self.sender_email, self.sender_password)
                # 发送邮件
                server.sendmail(
                    self.sender_email,
                    to_emails,
                    message.as_string(),
                )

            logger.info(
                "邮件发送成功: 主题='%s', 收件人=%s",
                subject,
                to_emails,
            )
            return ToolResult.success(
                self.name,
                message=f"邮件已成功发送给 {len(to_emails)} 个收件人",
                data={
                    "to_emails": to_emails,
                    "subject": subject.strip(),
                    "sender_email": self.sender_email,
                },
            )

        except smtplib.SMTPAuthenticationError as e:
            # 授权码错误
            error_msg = f"SMTP 认证失败，请检查授权码是否正确: {e}"
            logger.error(error_msg)
            return ToolResult.error(self.name, error_msg)

        except smtplib.SMTPRecipientsRefused as e:
            # 收件人被拒绝
            error_msg = f"收件人地址无效: {e}"
            logger.error(error_msg)
            return ToolResult.error(self.name, error_msg)

        except smtplib.SMTPException as e:
            # 其他 SMTP 错误
            error_msg = f"SMTP 发送失败: {e}"
            logger.error(error_msg)
            return ToolResult.error(self.name, error_msg)

        except Exception as e:
            # 捕获所有未预期的异常
            error_msg = f"邮件发送失败，未知错误: {e}"
            logger.error(error_msg)
            return ToolResult.error(self.name, error_msg)

    @staticmethod
    def _normalize_recipients(value: Any) -> list[str]:
        """目的：兼容逗号分隔字符串和列表形式的收件人输入。
        结果：返回去空白后的邮箱列表，非法输入抛出异常。
        """
        if isinstance(value, str):
            recipients = [item.strip() for item in value.split(",")]
        elif isinstance(value, list):
            recipients = [str(item).strip() for item in value]
        else:
            raise ValueError("收件人列表不能为空")
        return [item for item in recipients if item]

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        """目的：阻止空主题或空正文继续进入 SMTP 发送层。
        结果：返回清洗后的字符串，空值抛出 ValueError。
        """
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name}不能为空")
        return text

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        """目的：统一处理可选 HTML 正文等可空字段。
        结果：返回清洗后的字符串或 None。
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None
