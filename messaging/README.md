# messaging 模块说明

## 1. 模块定位

`messaging` 是消息队列适配层，负责把业务事件投递到 RocketMQ。

它解决的是“长期记忆等异步任务如何可靠进入消息队列”的问题。

## 2. 目录结构

- `memory_mq.py`
  作用：长期记忆 RocketMQ 适配器。
  功能：封装 RocketMQ Producer 创建、消息构造、发送和依赖错误提示。
- `__init__.py`
  作用：模块导出入口。
  功能：暴露消息队列相关能力。

## 3. 对外职责

- 提供长期记忆事件投递能力。
- 隔离 RocketMQ SDK 细节。
- 为 Outbox Relay 和后台任务提供统一消息发送入口。

## 4. 依赖边界

- 可以依赖 `core` 配置和 `agents.memory_events` 事件契约。
- 不直接处理长期记忆提取、向量写入或聊天主流程。
- Windows 本地主机不直接跑 RocketMQ Python SDK，当前稳定运行方式是 Docker 后台任务。

## 5. 企业规范做法

- 消息体统一使用契约对象，不在发送端临时拼字段。
- 生产者只负责投递，不负责消费后的业务处理。
- 投递失败由 MySQL Outbox 和 Relay 补偿，不在聊天主链路阻塞用户回复。

## 6. 维护要求

- 新增 Topic、Tag 或消费组时同步更新本 README、`.env.example`、`docker-compose.yml` 和对应消费者文档。
- 修改消息体字段时同步更新 `agents/memory_events.py`、Outbox 仓储和消费者测试。
