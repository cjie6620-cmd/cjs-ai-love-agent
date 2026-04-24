"""LangGraph StateGraph 编译：构建图拓扑 + 可选 PostgresSaver Checkpointer。

设计目的：将所有节点和条件边组装为可执行的 CompiledStateGraph，
支持通过 PostgresSaver 实现多轮对话状态持久化，
支持 LangSmith 链路追踪（LangGraph 自动读取 LANGSMITH_* 环境变量）。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from core.config import get_settings

# Windows 修复：psycopg 的 ProactorEventLoop 在 Windows 上与异步连接池不兼容
# 强制使用 SelectorEventLoop 以确保 PostgresSaver 正确初始化
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from .edges import (
    route_after_draft,
    route_after_generation,
    route_after_safety,
)
from .graph_state import CompanionState
from .nodes import (
    build_advisor_draft,
    finalize_advisor,
    generate_reply,
    output_guard,
    recall_memory,
    safety_check,
    search_knowledge,
)

logger = logging.getLogger(__name__)


class CompiledGraphProtocol(Protocol):
    """约束 LangGraph 编译结果的最小可用接口。
    
    目的：约束约束 LangGraph 编译结果的最小可用接口相关接口能力边界。
    结果：调用方可依赖统一协议而不耦合具体实现。
    """

    async def ainvoke(
        self,
        input: CompanionState,
        config: dict[str, object] | None = None,
    ) -> CompanionState:
        """执行 ainvoke 方法。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        ...

    def astream_events(
        self,
        input: CompanionState,
        config: dict[str, object] | None = None,
        *,
        version: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """执行 astream_events 方法。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        ...


_compiled_graph: CompiledGraphProtocol | None = None
_checkpointer_pool: AsyncConnectionPool[Any] | None = None


def _is_incompatible_windows_loop() -> bool:
    """判断当前事件循环是否与 psycopg 异步连接池不兼容。"""
    if sys.platform != "win32":
        return False

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False

    return "proactor" in loop.__class__.__name__.lower()


def _build_graph() -> StateGraph:
    """构建并返回未编译的 StateGraph（拓扑定义）。
    
    目的：执行构建并返回未编译的 StateGraph（拓扑定义）相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    graph = StateGraph(state_schema=CompanionState)

    # 注册所有节点
    graph.add_node("safety_check", safety_check)
    graph.add_node("build_advisor_draft", build_advisor_draft)
    graph.add_node("recall_memory", recall_memory)
    graph.add_node("search_knowledge", search_knowledge)
    graph.add_node("generate_reply", generate_reply)
    graph.add_node("finalize_advisor", finalize_advisor)
    graph.add_node("output_guard", output_guard)

    # 设置入口
    graph.set_entry_point("safety_check")

    # 条件边：安全检查 → 路由（所有安全级别均进入顾问构建）
    graph.add_conditional_edges(
        source="safety_check",
        path=route_after_safety,
        path_map={
            "build_advisor_draft": "build_advisor_draft",
        },
    )

    # 条件边：顾问草稿 → 启动并行召回
    graph.add_conditional_edges(
        source="build_advisor_draft",
        path=route_after_draft,
        path_map={
            "recall_memory": "recall_memory",
            "search_knowledge": "search_knowledge",
        },
    )

    # 并行分支：recall_memory 和 search_knowledge
    # 两者完成后（LangGraph Join 节点），进入 generate_reply
    graph.add_edge("recall_memory", "generate_reply")
    graph.add_edge("search_knowledge", "generate_reply")

    # generate_reply → finalize_advisor → output_guard → END
    graph.add_conditional_edges(
        source="generate_reply",
        path=route_after_generation,
        path_map={"finalize_advisor": "finalize_advisor"},
    )
    graph.add_edge("finalize_advisor", "output_guard")
    graph.add_edge("output_guard", END)

    return graph


def _compile_without_checkpointer() -> CompiledGraphProtocol:
    """编译不带持久化的图，作为默认和降级路径。
    
    目的：执行编译不带持久化的图，作为默认和降级路径相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return cast(CompiledGraphProtocol, _build_graph().compile())


async def initialize_graph_resources() -> None:
    """初始化编译图和 checkpointer 资源。

    目的：在应用启动时显式打开连接池并执行 checkpointer.setup()。
    结果：避免运行时首次请求才发现连接池未打开或 checkpoint 表不存在。
    """
    global _compiled_graph, _checkpointer_pool

    if _compiled_graph is not None:
        return

    settings = get_settings()
    graph = _build_graph()

    if not settings.langgraph_use_checkpointer:
        logger.info("LangGraph Checkpointer 未启用，以无持久化模式运行。")
        _compiled_graph = cast(CompiledGraphProtocol, graph.compile())
        return

    if _is_incompatible_windows_loop():
        logger.warning(
            "检测到 Windows ProactorEventLoop，psycopg 异步连接池不兼容，"
            "LangGraph Checkpointer 将跳过并以无持久化模式运行。"
        )
        _compiled_graph = cast(CompiledGraphProtocol, graph.compile())
        return

    pool: AsyncConnectionPool[Any] | None = None
    checkpoint_url = settings.langgraph_checkpoint_url or settings.vector_db_url
    psycopg_url = checkpoint_url.replace("postgresql+psycopg://", "postgresql://")
    try:
        pool = AsyncConnectionPool(
            conninfo=psycopg_url,
            open=False,
            min_size=1,
            max_size=5,
            timeout=3.0,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
                "connect_timeout": 3,
            },
        )
        await pool.open(wait=True, timeout=3.0)

        checkpointer = AsyncPostgresSaver(conn=cast(Any, pool))
        await checkpointer.setup()

        _checkpointer_pool = pool
        _compiled_graph = cast(CompiledGraphProtocol, graph.compile(checkpointer=checkpointer))
        logger.info("LangGraph Checkpointer 已初始化（URL: %s）", checkpoint_url)
    except Exception as exc:
        logger.warning("LangGraph Checkpointer 初始化失败，将降级运行: %s", exc)
        if pool is not None:
            await pool.close()
        _checkpointer_pool = None
        _compiled_graph = cast(CompiledGraphProtocol, graph.compile())


async def shutdown_graph_resources() -> None:
    """关闭 LangGraph 相关资源，避免连接池泄漏。
    
    目的：执行关闭 LangGraph 相关资源，避免连接池泄漏相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    global _compiled_graph, _checkpointer_pool

    if _checkpointer_pool is not None:
        await _checkpointer_pool.close()
        _checkpointer_pool = None
    _compiled_graph = None


def get_compiled_graph() -> CompiledGraphProtocol:
    """获取编译后的图；若尚未初始化则使用无持久化模式即时编译。
    
    目的：获取获取编译后的图；若尚未初始化则使用无持久化模式即时编译。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    global _compiled_graph

    if _compiled_graph is None:
        logger.info("LangGraph 资源尚未初始化，临时以无持久化模式编译图。")
        _compiled_graph = _compile_without_checkpointer()
    return _compiled_graph
