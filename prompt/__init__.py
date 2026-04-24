# -*- coding: utf-8 -*-
"""
提示词模板模块：提供 Agent 对话和知识检索相关的提示词构建函数。

目的：为整个项目提供统一的提示词构建能力，支持知识摘要生成、Agent 对话回复和记忆决策。
结果：导入本模块后，可以直接使用 build_rag_summary_prompt 函数生成知识文档摘要提示词。
"""

from .contracts import PromptSection, PromptSpec

# 默认知识分类常量，用于标识关系知识类别的文档
DEFAULT_KNOWLEDGE_CATEGORY = "relationship_knowledge"

def build_rag_summary_prompt(title: str, chunk_count: int) -> str:
    """
    构建知识文档摘要提示词。

    目的：生成用于告知 AI 知识文档已处理的提示词，
    使模型在后续检索时能够优先返回高相关片段。

    结果：返回格式化的提示词字符串，包含知识文档标题和片段数量信息。
    """
    return f"知识文档《{title}》已拆分为 {chunk_count} 个片段，后续检索优先返回高相关片段。"


__all__ = [
    "DEFAULT_KNOWLEDGE_CATEGORY",
    "PromptSection",
    "PromptSpec",
    "build_rag_summary_prompt",
]
