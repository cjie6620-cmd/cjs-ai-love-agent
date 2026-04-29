"""文档解析抽象：策略模式入口。

目的：定义文档解析的抽象接口和基础数据结构，为不同文件格式的解析器提供统一的契约，
使文档摄入流程可以通过策略模式灵活切换解析器，同时保持数据结构的统一性。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedDocument:
    """目的：封装特定格式的解析逻辑，将原始内容转换为标准文本结果。
    结果：上游流程可以复用统一解析接口处理不同文件类型，降低适配成本。
    """

    # 目的：保存 text 字段，用于 ParsedDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 text 值。
    text: str
    # 目的：保存 metadata 字段，用于 ParsedDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata 值。
    metadata: dict[str, Any] = field(default_factory=dict)


class ParseError(Exception):
    """目的：表达特定场景下的异常语义，方便上层统一识别和处理失败分支。
    结果：调用方可以按异常类型捕获并执行对应的降级、重试或告警逻辑。
    """


class DocumentParser(ABC):
    """目的：封装特定格式的解析逻辑，将原始内容转换为标准文本结果。
    结果：上游流程可以复用统一解析接口处理不同文件类型，降低适配成本。
    """

    @abstractmethod
    def supports(self, mime: str | None, suffix: str) -> bool:
        """目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
        结果：返回标准化解析结果，便于后续链路复用和扩展。
        """

    @abstractmethod
    def parse(self, data: bytes, *, filename: str = "") -> ParsedDocument:
        """目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
        结果：返回标准化解析结果，便于后续链路复用和扩展。
        """
