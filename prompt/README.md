# prompt 模块说明

## 1. 模块定位

`prompt` 是提示词管理模块，负责 Prompt 契约定义、模板仓库管理和模板渲染入口。

它解决的是“提示词如何标准化、版本化、可替换”的问题。

## 2. 目录结构

- `contracts.py`
  作用：Prompt 契约定义。
  功能：定义可渲染、可追踪、可复用的 Prompt 结构。
- `repository.py`
  作用：Prompt 仓库。
  功能：统一处理本地模板与 LangSmith Prompt 拉取。
- `templates/agent.py`
  作用：Agent 对话模板。
  功能：生成聊天主链路相关提示词。
- `templates/analysis.py`
  作用：分析模板。
  功能：生成分析、总结、判断类提示词。
- `templates/rag.py`
  作用：RAG 模板。
  功能：生成知识检索和证据注入类提示词。
- `tests/`
  作用：提示词模块测试。
  功能：验证契约和模板仓储行为。
- `__init__.py`
  作用：模块导出入口。
  功能：统一暴露模板构建能力。

## 3. 对外职责

- 提供统一 Prompt 渲染入口。
- 管理 Prompt 版本与来源。
- 为 Agent、RAG、LLM 层提供稳定输入。

## 4. 依赖边界

- 可以依赖：`contracts`、`observability`
- 不应依赖路由、数据库和页面逻辑。
- 业务模块不应自行硬编码长 Prompt，优先走模板层。

## 5. 企业规范做法

- Prompt 要模板化、参数化、可追踪。
- Prompt 文本与业务逻辑分离，便于迭代和实验。
- 本地模板与远端模板来源要可切换、可回退。
- 重要 Prompt 要记录版本与用途。

## 6. 维护要求

- 新增模板文件时同步更新本 README。
- 调整 Prompt 合约字段时同步检查调用方兼容性。
