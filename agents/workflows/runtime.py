"""工作流运行时依赖。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Callable

from core.config import Settings, get_settings
from llm import LlmClient
from rag.retriever import KnowledgeRetriever
from security import SafetyGuard

from ..memory import MemoryManager

# @dataclass(slots=True) =
# 自动生成数据类 + 使用 __slots__ 优化内存结构，减少对象开销，提高访问性能，同时限制动态属性添加
# 等价写法（底层理解）
# @dataclass(slots=True)
# class A:
#     x: int
#
# ≈
#
# class A:
#     __slots__ = ('x',)
#
#     def __init__(self, x):
#         self.x = x
#
# 👉 本质：
#
# slots=True 就是自动帮你加了 __slots__
@dataclass(slots=True)
class WorkflowRuntime:
    """工作流节点执行时需要的依赖集合。

    目的：定义运行时依赖或协作边界，统一工作流节点之间的调用约束。
    结果：相关模块可以围绕相同接口稳定协作，降低接入和替换成本。
    """

    settings: Settings
    llm_client_factory: Callable[[], LlmClient]
    memory_manager: MemoryManager
    knowledge_retriever: KnowledgeRetriever
    safety_guard: SafetyGuard

    def build_llm_client(self) -> LlmClient:
        """构建目标对象或结构。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        return self.llm_client_factory()


workflow_runtime_var: ContextVar[WorkflowRuntime | None] = ContextVar(
    "workflow_runtime_var",
    default=None,
)


def activate_workflow_runtime(runtime: WorkflowRuntime) -> Token[WorkflowRuntime | None]:
    """将运行时依赖绑定到当前上下文。
    
    目的：执行将运行时依赖绑定到当前上下文相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return workflow_runtime_var.set(runtime)


def reset_workflow_runtime(token: Token[WorkflowRuntime | None]) -> None:
    """重置当前上下文中的工作流运行时依赖。
    
    目的：执行重置当前上下文中的工作流运行时依赖相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    workflow_runtime_var.reset(token)


def get_workflow_runtime() -> WorkflowRuntime:
    """从当前上下文读取工作流运行时依赖。
    
    目的：获取从当前上下文读取工作流运行时依赖。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    runtime = workflow_runtime_var.get()
    if runtime is None:
        raise RuntimeError("工作流运行时依赖未注入")
    return runtime


def build_workflow_runtime(
    *,
    settings: Settings | None = None,
    llm_client_factory: Callable[[], LlmClient] | None = None,
    memory_manager: MemoryManager | None = None,
    knowledge_retriever: KnowledgeRetriever | None = None,
    safety_guard: SafetyGuard | None = None,
) -> WorkflowRuntime:
    """构建默认工作流运行时依赖。
    
    目的：构建构建默认工作流运行时依赖所需的数据或对象。
    结果：返回后续流程可直接消费的构建结果。
    """
    resolved_settings = settings or get_settings()
    return WorkflowRuntime(
        settings=resolved_settings,
        llm_client_factory=llm_client_factory or LlmClient,
        memory_manager=memory_manager or MemoryManager(),
        knowledge_retriever=knowledge_retriever or KnowledgeRetriever(),
        safety_guard=safety_guard or SafetyGuard(),
    )
