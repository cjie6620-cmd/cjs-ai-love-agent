"""LangGraph 条件边路由函数：基于安全级别和对话模式决定下一跳节点。

设计目的：根据 CompanionState 中的 safety_level、mode 等字段，
在图的分支点决定路由方向，实现安全短路口和并行节点路由。
"""

from __future__ import annotations

from typing import Literal

from .graph_state import CompanionState


def route_after_safety(state: CompanionState) -> Literal["build_advisor_draft"]:
    """目的：执行安全检查后路由：所有安全级别均进入顾问构建，确保 output_guard 执行相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return "build_advisor_draft"


def route_after_draft(
    state: CompanionState,
) -> list[Literal["recall_memory", "search_knowledge"]]:
    """目的：执行顾问草稿构建后路由：启动记忆召回和知识检索并行分支相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return ["recall_memory", "search_knowledge"]


def route_after_generation(state: CompanionState) -> Literal["finalize_advisor"]:
    """目的：执行回复生成后路由：进入顾问完成节点相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return "finalize_advisor"
