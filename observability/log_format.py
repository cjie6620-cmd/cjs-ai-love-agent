"""日志内容格式化工具。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_MAX_STRING_LENGTH = 2000
DEFAULT_MAX_LIST_ITEMS = 30
DEFAULT_MAX_DEPTH = 8


def format_pretty_json_log(payload: Mapping[str, Any], *, max_string_length: int = DEFAULT_MAX_STRING_LENGTH) -> str:
    """把日志载荷格式化成适合本地排查的缩进 JSON。"""
    safe_payload = compact_log_value(payload, max_string_length=max_string_length)
    return json.dumps(safe_payload, ensure_ascii=False, indent=2, default=str)


def compact_log_value(
    value: Any,
    *,
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
    max_list_items: int = DEFAULT_MAX_LIST_ITEMS,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Any:
    """递归压缩日志内容，避免超长 prompt 或 schema 把控制台刷屏。"""
    return _compact_value(
        value,
        max_string_length=max_string_length,
        max_list_items=max_list_items,
        max_depth=max_depth,
        depth=0,
    )


def _compact_value(
    value: Any,
    *,
    max_string_length: int,
    max_list_items: int,
    max_depth: int,
    depth: int,
) -> Any:
    if depth >= max_depth:
        return _summarize_leaf(value)

    if isinstance(value, str):
        return _truncate_string(value, max_string_length)

    if isinstance(value, Mapping):
        return {
            str(key): _compact_value(
                item,
                max_string_length=max_string_length,
                max_list_items=max_list_items,
                max_depth=max_depth,
                depth=depth + 1,
            )
            for key, item in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        items = list(value)
        compacted = [
            _compact_value(
                item,
                max_string_length=max_string_length,
                max_list_items=max_list_items,
                max_depth=max_depth,
                depth=depth + 1,
            )
            for item in items[:max_list_items]
        ]
        if len(items) > max_list_items:
            compacted.append({"_truncated_items": len(items) - max_list_items})
        return compacted

    return value


def _truncate_string(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    omitted = len(value) - max_length
    return f"{value[:max_length]}... [已截断 {omitted} 字符]"


def _summarize_leaf(value: Any) -> str:
    if isinstance(value, Mapping):
        return f"[Object: {len(value)} keys]"
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return f"[Array: {len(value)} items]"
    return str(value)
