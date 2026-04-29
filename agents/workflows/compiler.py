"""LangGraph StateGraph 编译：构建图拓扑并强制启用 PostgresSaver Checkpointer。

设计目的：将所有节点和条件边组装为可执行的 CompiledStateGraph，
通过 PostgresSaver 实现多轮对话状态持久化，
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
    """目的：约束约束 LangGraph 编译结果的最小可用接口相关接口能力边界。
    结果：调用方可依赖统一协议而不耦合具体实现。
    """

    async def ainvoke(
        self,
        input: CompanionState,
        config: dict[str, object] | None = None,
    ) -> CompanionState:
        """目的：封装一次外部能力或链路调用，统一入参与异常处理。
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
        """目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        ...


_compiled_graph: CompiledGraphProtocol | None = None
_checkpointer_pool: AsyncConnectionPool[Any] | None = None


def _is_incompatible_windows_loop() -> bool:
    """目的：识别 Windows ProactorEventLoop 场景，避免异步 Postgres 连接池初始化失败。
    结果：返回 True 表示应跳过 checkpointer 并使用无持久化图。
    """
    if sys.platform != "win32":
        return False

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False

    return "proactor" in loop.__class__.__name__.lower()


def _build_graph() -> StateGraph:
    """目的：执行构建并返回未编译的 StateGraph（拓扑定义）相关逻辑。
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
async def initialize_graph_resources() -> None:
    """目的：在应用启动时显式打开连接池并执行 checkpointer.setup()。
    结果：避免运行时首次请求才发现连接池未打开或 checkpoint 表不存在。
    """
    global _compiled_graph, _checkpointer_pool

    if _compiled_graph is not None:
        return

    settings = get_settings()
    graph = _build_graph()

    if _is_incompatible_windows_loop():
        raise RuntimeError(
            "检测到 Windows ProactorEventLoop，psycopg 异步连接池不兼容，"
            "当前项目已不再支持无持久化降级运行。"
            "请使用启动参数 --loop core.event_loop:windows_compatible_loop_factory。"
        )

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
        logger.error("LangGraph Checkpointer 初始化失败，服务启动中止: %s", exc)
        if pool is not None:
            await pool.close()
        _checkpointer_pool = None
        raise RuntimeError("LangGraph Checkpointer 初始化失败，当前项目要求持久化可用后再启动。") from exc


async def shutdown_graph_resources() -> None:
    """目的：执行关闭 LangGraph 相关资源，避免连接池泄漏相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    global _compiled_graph, _checkpointer_pool

    if _checkpointer_pool is not None:
        await _checkpointer_pool.close()
        _checkpointer_pool = None
    _compiled_graph = None


def get_compiled_graph() -> CompiledGraphProtocol:
    """目的：获取已经初始化完成的编译图，避免绕过持久化依赖检查。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    global _compiled_graph

    if _compiled_graph is None:
        raise RuntimeError("LangGraph 编译图尚未初始化，请先执行 initialize_graph_resources()。")
    return _compiled_graph
