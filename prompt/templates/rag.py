# -*- coding: utf-8 -*-
"""
RAG 场景复用聊天主 Prompt 模板。

目的：提供 RAG 检索增强聊天的 PromptSpec 构建入口。
结果：导出 build_chat_reply_prompt_spec 函数，支持知识检索增强的对话回复。
"""

from .agent import build_chat_reply_prompt_spec

__all__ = ["build_chat_reply_prompt_spec"]
