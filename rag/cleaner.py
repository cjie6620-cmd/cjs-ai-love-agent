"""文档清洗：在切片前去掉常见噪声。"""

from __future__ import annotations

import re
from typing import Any


class TextCleaner:
    """离线建库前的轻量清洗器。"""

    _page_number_re = re.compile(r"(?m)^\s*(?:第\s*\d+\s*页|\d+\s*/\s*\d+|Page\s+\d+)\s*$")
    _catalog_re = re.compile(
        r"(?m)^\s*(?:目录\s*)?(?:[\d一二三四五六七八九十]+[.\s、-]*)?.*\.{3,}\s*\d+\s*$"
    )
    _multi_blank_re = re.compile(r"\n{3,}")
    _header_footer_re = re.compile(
        r"(?m)^\s*(?:版权所有|机密|Confidential|All Rights Reserved).*$"
    )
    _broken_line_re = re.compile(r"(?<=[^\n。！？；;:])\n(?=[^\n#\-\*\d])")
    _spaces_re = re.compile(r"[ \t]{2,}")
    _repeat_heading_re = re.compile(r"(?m)^(#{1,6}\s+.+)\n\1$")

    def clean(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        """执行清洗并返回结果。"""
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
        """按文档类型合并 OCR/PDF 断行。"""
        parser = str(metadata.get("parser", "")).lower()
        if parser in {"pdf", "docx", "pptx", "plain"}:
            return self._broken_line_re.sub(" ", text)
        return text
