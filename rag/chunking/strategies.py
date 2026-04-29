"""切分策略实现：固定窗口、Markdown 标题、父子块。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .base import ChunkStrategy, TextChunk


@dataclass(slots=True)
class _MarkdownSection:
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 heading_title 字段，用于 _MarkdownSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_title 值。
    heading_title: str
    # 目的：保存 heading_path 字段，用于 _MarkdownSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_path 值。
    heading_path: str
    # 目的：保存 heading_level 字段，用于 _MarkdownSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_level 值。
    heading_level: int
    # 目的：保存 body 字段，用于 _MarkdownSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 body 值。
    body: str
    # 目的：保存 section_index 字段，用于 _MarkdownSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 section_index 值。
    section_index: int


def _normalize_text(text: str) -> str:
    """目的：标准化文本换行符，确保在不同操作系统下处理结果一致。
    结果：返回标准化换行符后的文本。
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_heading_text(title: str) -> str:
    """目的：清理Markdown标题中的多余符号，提取干净的标题文本。
    结果：返回清理后的标题文本。
    """
    cleaned = re.sub(r"\s+#+\s*$", "", title.strip())
    return re.sub(r"\s+", " ", cleaned)


def _compose_section_text(heading_path: str, body: str) -> str:
    """目的：将标题路径和正文组合成完整的文本块，用于后续的向量化处理。
    结果：返回组合后的完整文本块。
    """
    body = body.strip()
    if heading_path and body:
        return f"{heading_path}\n\n{body}"
    if heading_path:
        return heading_path
    return body


def _extract_markdown_sections(
    text: str,
    heading_re: re.Pattern[str],
) -> list[_MarkdownSection]:
    """目的：解析Markdown文档，提取所有章节及其层级结构信息。
    结果：返回包含章节信息的 _MarkdownSection 列表。
    """
    normalized = _normalize_text(text)
    matches = list(heading_re.finditer(normalized))
    if not matches:
        body = normalized.strip()
        return [_MarkdownSection("", "", 0, body, 0)] if body else []

    sections: list[_MarkdownSection] = []
    section_index = 0

    preface = normalized[: matches[0].start()].strip()
    if preface:
        sections.append(_MarkdownSection("", "", 0, preface, section_index))
        section_index += 1

    heading_stack: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = _normalize_heading_text(match.group(2))

        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, title))

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(normalized)
        body = normalized[start:end].strip()
        heading_path = " / ".join(item[1] for item in heading_stack)
        sections.append(
            _MarkdownSection(
                heading_title=title,
                heading_path=heading_path,
                heading_level=level,
                body=body,
                section_index=section_index,
            ),
        )
        section_index += 1
    return sections


def _split_by_markdown_headings(text: str, heading_re: re.Pattern[str]) -> list[tuple[str, str]]:
    """目的：将Markdown文档按标题分割为多个文本块，每个块包含标题路径和内容。
    结果：返回 (标题路径, 章节文本) 元组列表。
    """
    return [
        (section.heading_path, _compose_section_text(section.heading_path, section.body))
        for section in _extract_markdown_sections(text, heading_re)
        if _compose_section_text(section.heading_path, section.body)
    ]


def _build_stable_parent_id(
    *,
    section: _MarkdownSection,
    base_metadata: dict[str, Any],
) -> str:
    """目的：创建稳定的父块ID，确保在不同进程和会话中保持一致性。
    结果：返回稳定生成的 parent_id 字符串。
    """
    scope = [
        str(base_metadata.get("doc_id", "")),
        str(base_metadata.get("document_id", "")),
        str(base_metadata.get("filename", "")),
        str(base_metadata.get("title", "")),
        str(base_metadata.get("source", "")),
        str(base_metadata.get("category", "")),
        str(section.section_index),
        str(section.heading_level),
        section.heading_path,
        section.body,
    ]
    digest = hashlib.blake2s("||".join(scope).encode("utf-8"), digest_size=8).hexdigest()
    return f"p_{digest}"


class FixedSizeChunkStrategy(ChunkStrategy):
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    def __init__(self, chunk_size: int = 800, overlap: int = 120) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("chunk_size 与 overlap 配置无效")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, base_metadata: dict[str, Any] | None = None) -> list[TextChunk]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        base = dict(base_metadata or {})
        if not text.strip():
            return []
        chunks: list[TextChunk] = []
        start = 0
        idx = 0
        n = len(text)
        step = self.chunk_size - self.overlap
        while start < n:
            end = min(start + self.chunk_size, n)
            piece = text[start:end].strip()
            if piece:
                meta = {
                    **base,
                    "chunk_index": idx,
                    "start_offset": start,
                    "end_offset": end,
                    "char_count": len(piece),
                    "strategy": "fixed_size",
                }
                chunks.append(TextChunk(text=piece, metadata=meta))
                idx += 1
            if end >= n:
                break
            start += step
        return chunks


class MarkdownHeadingChunkStrategy(ChunkStrategy):
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 _heading 字段，用于 MarkdownHeadingChunkStrategy 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _heading 值。
    _heading = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, max_chunk_chars: int = 1200, overlap: int = 100) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self._secondary = FixedSizeChunkStrategy(chunk_size=max_chunk_chars, overlap=overlap)

    def split(self, text: str, base_metadata: dict[str, Any] | None = None) -> list[TextChunk]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        base = dict(base_metadata or {})
        if not text.strip():
            return []
        sections = _extract_markdown_sections(text, self._heading)
        out: list[TextChunk] = []
        for section in sections:
            section_text = _compose_section_text(section.heading_path, section.body)
            if not section_text:
                continue
            sub_meta = {
                **base,
                "heading_path": section.heading_path,
                "heading_title": section.heading_title,
                "heading_level": section.heading_level,
                "section_index": section.section_index,
                "strategy": "markdown_heading",
            }
            sub_chunks = self._secondary.split(section_text, sub_meta)
            for ch in sub_chunks:
                ch.metadata["strategy"] = "markdown_heading"
            out.extend(sub_chunks)
        return out

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return _split_by_markdown_headings(text, self._heading)


class ParentChildChunkStrategy(ChunkStrategy):
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 _heading 字段，用于 ParentChildChunkStrategy 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 _heading 值。
    _heading = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, child_size: int = 500, child_overlap: int = 80) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self._child = FixedSizeChunkStrategy(chunk_size=child_size, overlap=child_overlap)

    def split(self, text: str, base_metadata: dict[str, Any] | None = None) -> list[TextChunk]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        base = dict(base_metadata or {})
        if not text.strip():
            return []
        sections = _extract_markdown_sections(text, self._heading)
        out: list[TextChunk] = []
        for section in sections:
            parent_text = _compose_section_text(section.heading_path, section.body)
            if not parent_text:
                continue
            parent_id = _build_stable_parent_id(section=section, base_metadata=base)
            parent_meta = {
                **base,
                "chunk_role": "parent",
                "parent_id": parent_id,
                "logical_chunk_id": parent_id,
                "heading_path": section.heading_path,
                "heading_title": section.heading_title,
                "heading_level": section.heading_level,
                "section_index": section.section_index,
                "child_count": 0,
                "char_count": len(parent_text),
                "strategy": "parent_child",
            }
            parent_chunk = TextChunk(text=parent_text, metadata=parent_meta)

            child_base = {
                **base,
                "parent_id": parent_id,
                "heading_path": section.heading_path,
                "heading_title": section.heading_title,
                "heading_level": section.heading_level,
                "section_index": section.section_index,
            }
            child_chunks = self._child.split(parent_text, child_base)
            parent_chunk.metadata["child_count"] = len(child_chunks)
            out.append(parent_chunk)

            for child_index, chunk in enumerate(child_chunks):
                chunk.metadata["chunk_role"] = "child"
                chunk.metadata["parent_id"] = parent_id
                chunk.metadata["logical_chunk_id"] = f"{parent_id}_c_{child_index}"
                chunk.metadata["child_index"] = child_index
                chunk.metadata["child_count"] = len(child_chunks)
                chunk.metadata["char_count"] = len(chunk.text)
                chunk.metadata["strategy"] = "parent_child"
                out.append(chunk)
        return out


def default_chunk_strategies() -> dict[str, ChunkStrategy]:
    """目的：提供默认的切分策略映射，便于通过名称选择合适的切分策略。
    结果：返回策略名称到策略实例的字典映射。
    """
    return {
        "fixed": FixedSizeChunkStrategy(),
        "markdown": MarkdownHeadingChunkStrategy(),
        "parent_child": ParentChildChunkStrategy(),
    }
