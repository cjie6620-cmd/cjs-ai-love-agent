# agents 模块说明

## 1. 模块定位

`agents` 是业务智能编排层，负责把 LLM、Prompt、RAG、记忆、安全治理和流式输出串成一个可执行的 Agent 主流程。

这个模块解决的是“用户发来一句话后，系统如何完成分析、召回、生成、保存与返回”的问题。

## 2. 目录结构

- `agent_service.py`
  作用：Agent 对外服务入口。
  功能：接收聊天请求，协调工作流、缓存、会话持久化和记忆写入。
- `memory.py`
  作用：记忆管理模块。
  功能：管理长期记忆与会话短期记忆，负责读写与归档。
- `question_advisor.py`
  作用：问题顾问模块。
  功能：补全检索查询、提炼问题摘要、生成追问建议。
- `worker.py`
  作用：异步任务入口。
  功能：承接知识索引、记忆提炼等后台任务。
- `tools/`
  作用：Agent 可用工具封装。
  功能：放置天气、邮件、数据库等工具适配层。
- `workflows/`
  作用：LangGraph 工作流编排。
  功能：定义节点、边、状态、运行时与编译逻辑。
- `tests/`
  作用：模块级测试。
  功能：验证回复、顾问、工作流等核心行为。
- `__init__.py`
  作用：模块公共出口。
  功能：统一导出常用服务或类型。

## 3. 对外职责

- 提供聊天主流程服务。
- 统一管理 Agent 状态流转。
- 组织记忆召回、知识检索和回复生成。
- 负责对话结束后的持久化与缓存回填。

## 4. 依赖边界

- 可以依赖：`contracts`、`prompt`、`llm`、`rag`、`security`、`persistence`、`observability`、`stream`
- 不建议反向被底层模块依赖。
- 路由层只调用 `AgentService` 这类稳定入口，不直接进入 `workflows` 内部细节。

## 5. 企业规范做法

- 服务入口统一收敛到 Service 层，路由层不直接拼工作流。
- 工作流编排与业务逻辑分离，节点职责单一。
- 工具适配统一放在 `tools/`，禁止在节点里散落第三方 SDK 直调。
- 状态对象、输入输出对象必须使用共享契约，避免字典到处漂移。
- 涉及缓存、持久化、异步任务的地方，要明确主路径与降级路径。
- 新增 Agent 能力时，优先补测试，再补节点，再补入口装配。

## 6. 维护要求

- 新增文件后同步更新本 README。
- 新增工作流节点时，要同时更新“节点职责”和“调用链说明”。
- 影响主链路的改动必须补充回归测试。

## 7. 主链路执行流程

下面这条链路描述的是一次聊天请求进入 `agents` 模块后的核心执行过程：

```text
用户请求 ChatRequest
        |
        v
langgraph_adapter.py
CompanionGraphWorkflow.run()/stream()
        |
        | 1. 构造初始状态
        | 2. 注入 runtime
        v
graph_state.py
CompanionState
(整个图共享的状态对象)
        |
        | 由 adapter 调用
        v
compiler.py
_build_graph() + compile()
        |
        | 注册节点 / 边 / 入口
        v
CompiledStateGraph
        |
        | 从入口节点开始执行
        v
+------------------------+
| nodes.py               |
| safety_check           |
+------------------------+
        |
        | 路由规则
        v
+------------------------+
| edges.py               |
| route_after_safety     |
+------------------------+
        |
        v
+------------------------+
| nodes.py               |
| build_advisor_draft    |
+------------------------+
        |
        | 路由为并行分支
        v
+------------------------+       +------------------------+
| nodes.py               |       | nodes.py               |
| recall_memory          |       | search_knowledge       |
+------------------------+       +------------------------+
        |                               |
        |                               |
        +---------------+---------------+
                        |
                        | 状态合并
                        v
                graph_state.py
                CompanionState reducer
                        |
                        v
+------------------------+
| nodes.py               |
| generate_reply         |
+------------------------+
        |
        | 路由规则
        v
+------------------------+
| edges.py               |
| route_after_generation |
+------------------------+
        |
        v
+------------------------+
| nodes.py               |
| finalize_advisor       |
+------------------------+
        |
        v
+------------------------+
| nodes.py               |
| output_guard           |
+------------------------+
        |
        v
最终状态 CompanionState
        |
        v
langgraph_adapter.py
_state_to_response()
        |
        v
ChatResponse / SSE 流式输出
```
