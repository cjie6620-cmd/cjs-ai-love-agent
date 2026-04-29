"""文档清洗：在切片前去掉常见噪声。

目的：统一清理页码、目录、页眉页脚、重复标题和断行等建库噪声。
结果：输出更适合切片、向量化和 BM25 索引的文本。
"""

from __future__ import annotations

import re
from typing import Any


class TextCleaner:
    """目的：封装常见文档噪声规则，减少索引管道中的清洗细节。
    结果：调用 clean 后获得格式更稳定的纯文本。
    """

    # 目的：保存 _page_number_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _page_number_re 值。
    _page_number_re = re.compile(r"(?m)^\s*(?:第\s*\d+\s*页|\d+\s*/\s*\d+|Page\s+\d+)\s*$")
    # 目的：保存 _catalog_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _catalog_re 值。
    _catalog_re = re.compile(
        r"(?m)^\s*(?:目录\s*)?(?:[\d一二三四五六七八九十]+[.\s、-]*)?.*\.{3,}\s*\d+\s*$"
    )
    # 目的：保存 _multi_blank_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _multi_blank_re 值。
    _multi_blank_re = re.compile(r"\n{3,}")
    # 目的：保存 _header_footer_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _header_footer_re 值。
    _header_footer_re = re.compile(
        r"(?m)^\s*(?:版权所有|机密|Confidential|All Rights Reserved).*$"
    )
    # 目的：保存 _broken_line_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _broken_line_re 值。
    _broken_line_re = re.compile(r"(?<=[^\n。！？；;:])\n(?=[^\n#\-\*\d])")
    # 目的：保存 _spaces_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _spaces_re 值。
    _spaces_re = re.compile(r"[ \t]{2,}")
    # 目的：保存 _repeat_heading_re 字段，用于 TextCleaner 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _repeat_heading_re 值。
    _repeat_heading_re = re.compile(r"(?m)^(#{1,6}\s+.+)\n\1$")

    def clean(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        """目的：按统一规则处理换行、空格、页码、目录和页眉页脚噪声。
        结果：返回去除噪声后的文本，空输入返回空字符串。
        """
        if not text.strip():
            return ""

        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = cleaned.replace("\u3000", " ")
        cleaned = self._page_number_re.sub("", cleaned)
        cleaned = self._catalog_re.sub("", cleaned)
        cleaned = self._header_footer_re.sub("", cleaned)
        cleaned = self._repeat_heading_re.sub(r"\1", cleaned)
        cleaned = self._merge_broken_lines(cleaned, metadata or {})
        cleaned = self._spaces_re.sub(" ", cleaned)
        cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
        cleaned = self._multi_blank_re.sub("\n\n", cleaned)
        return cleaned.strip()

    def _merge_broken_lines(self, text: str, metadata: dict[str, Any]) -> str:
        """目的：对 PDF、Office 和纯文本解析结果修复非段落换行。
        结果：返回断行被合并后的文本，Markdown 等结构化文本保持原样。
        """
        parser = str(metadata.get("parser", "")).lower()
        if parser in {"pdf", "docx", "pptx", "plain"}:
            return self._broken_line_re.sub(" ", text)
        return text
