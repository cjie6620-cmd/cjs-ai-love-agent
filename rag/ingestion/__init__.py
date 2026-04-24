"""文档摄入模块：提供多种格式文档的解析和文本提取功能。

目的：作为 ingestion 子包的入口，统一导出文档解析器注册表 ParserRegistry，
使文档摄入流程可以根据文件扩展名自动选择合适的解析器，
支持 Markdown、TXT、PDF 等多种文档格式的文本提取。
结果：导出 ParserRegistry 类。
"""

from .registry import ParserRegistry

__all__ = ["ParserRegistry"]
