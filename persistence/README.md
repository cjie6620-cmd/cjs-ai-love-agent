# persistence 模块说明

## 1. 模块定位

`persistence` 是持久化层，负责数据库基座、ORM 模型和仓储实现。

它解决的是“认证、对话、安全事件、长期记忆 Outbox 等数据如何稳定落库与查询”的问题。

## 2. 目录结构

- `db_base.py`
  作用：数据库基础设施。
  功能：管理引擎、Session 和 ORM 基类。
- `models.py`
  作用：ORM 模型定义。
  功能：定义用户、认证账号、刷新令牌、会话、消息、安全事件和长期记忆 Outbox 等数据表映射。
- `auth_repository.py`
  作用：认证仓储。
  功能：负责账号创建、账号查询、用户查询、refresh token 保存和吊销。
- `conversation_repository.py`
  作用：会话仓储。
  功能：负责会话与消息的保存、读取、历史查询和访客会话归并。
- `memory_outbox_repository.py`
  作用：长期记忆 Outbox 仓储。
  功能：负责长期记忆事件的可靠投递补偿状态管理。
- `safety_event_repository.py`
  作用：安全事件仓储。
  功能：负责安全审计事件写入和查询。
- `tests/`
  作用：持久化层测试。
  功能：验证仓储行为与装配结果。
- `__init__.py`
  作用：统一出口。
  功能：聚合基础设施、模型与仓储。

## 3. 对外职责

- 提供稳定的数据库访问能力。
- 通过 Repository 向业务层暴露数据操作。
- 维护认证、会话、安全审计、Outbox 的统一 ORM 映射。
- 隔离 ORM 细节和 SQL 细节。

## 4. 依赖边界

- 可以依赖：`core` 配置
- 不应反向依赖 `agents`、`api` 等上层业务模块。
- 业务层通过 Repository 访问数据，不直接操作 Session。

## 5. 企业规范做法

- ORM 模型、仓储实现、数据库连接管理分层维护。
- Repository 统一对外暴露查询与保存能力。
- 禁止在业务代码里散写原始 SQL 和 Session 提交逻辑。
- 表结构变化要同步 SQL、模型、仓储和文档。
- 认证表变化要同步 `sql/mysql_init.sql`、`models.py`、`auth_repository.py` 和接口契约。

## 6. 维护要求

- 新增表或仓储时同步更新本 README。
- 影响查询路径的改动必须补持久化测试。
