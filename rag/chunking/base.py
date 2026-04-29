"""文本切分抽象：策略模式。

目的：定义文本切分的抽象接口和数据结构，为不同类型的切分策略提供统一的基础框架，
使文档处理流程可以灵活切换切分策略，同时保持数据结构的统一性。
结果：提供统一的 TextChunk 数据结构和 ChunkStrategy 抽象基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextChunk:
    """目的：封装单个切片，带可追溯元数据相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    # 目的：保存 text 字段，用于 TextChunk 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 text 值。
    text: str
    # 目的：保存 metadata 字段，用于 TextChunk 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata 值。
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkStrategy(ABC):
    """目的：封装特定格式的解析逻辑，将原始内容转换为标准文本结果。
    结果：上游流程可以复用统一解析接口处理不同文件类型，降低适配成本。
    """

    @abstractmethod
    def split(self, text: str, base_metadata: dict[str, Any] | None = None) -> list[TextChunk]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
