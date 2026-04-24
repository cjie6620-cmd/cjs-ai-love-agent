"""Agent 工作流模块初始化：对外暴露 LangGraph 对话工作流接口。

目的：作为 workflows 子包的入口，统一导出对话工作流类 CompanionGraphWorkflow，
封装 LangGraph StateGraph 的编排逻辑。
结果：为 AgentService 提供统一的 run/stream 调用接口，使上层业务逻辑无需关心底层图执行细节。
"""

from .langgraph_adapter import CompanionGraphWorkflow
from .runtime import WorkflowRuntime, build_workflow_runtime

__all__ = ["CompanionGraphWorkflow", "WorkflowRuntime", "build_workflow_runtime"]
