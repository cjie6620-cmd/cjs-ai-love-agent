from __future__ import annotations

from llm.providers.base import _summarize_messages_for_log


def test_summarize_messages_splits_multiline_content_for_log() -> None:
    messages = [
        {
            "role": "system",
            "content": "prompt_name=chat.reply\n<role>\n你是助手\n</role>",
        }
    ]

    summaries = _summarize_messages_for_log(messages)

    assert summaries == [
        {
            "index": 0,
            "role": "system",
            "content_lines": [
                "prompt_name=chat.reply",
                "<role>",
                "你是助手",
                "</role>",
            ],
        }
    ]


def test_summarize_messages_keeps_single_line_content_for_log() -> None:
    messages = [{"role": "user", "content": "你好"}]

    summaries = _summarize_messages_for_log(messages)

    assert summaries == [{"index": 0, "role": "user", "content": "你好"}]
