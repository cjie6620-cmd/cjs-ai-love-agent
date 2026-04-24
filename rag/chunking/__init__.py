"""文档分块模块：提供多种文本分块策略将长文档拆分为可检索的片段。

目的：作为 chunking 子包的入口，统一导出文本分块相关的数据结构和分块策略，
使文档摄入流程可以根据不同文档类型选择合适的分块策略，
确保分块后的文本片段既保持语义完整性又便于向量检索。
结果：导出 TextChunk 和三种分块策略类。
"""

from .base import TextChunk
from .strategies import (
    FixedSizeChunkStrategy,
    MarkdownHeadingChunkStrategy,
    ParentChildChunkStrategy,
)

__all__ = [
    "TextChunk",
    "FixedSizeChunkStrategy",
    "MarkdownHeadingChunkStrategy",
    "ParentChildChunkStrategy",
]
