# AI Love Agent

面向情感陪伴、恋爱沟通、风格复刻、长期记忆与安全治理的企业级 AI Agent 工程骨架。

## 项目结构

```text
ai-love/
  app.py            # FastAPI 应用装配入口
  api/              # 路由与依赖
  agents/           # Agent 服务、工作流、记忆消费者与工具
  contracts/        # 共享请求/响应契约
  core/             # 配置与容器装配
  docker/           # 中间件、后台任务和辅助服务镜像配置
  docs/             # 知识库语料与补充文档
  frontend/         # Vue3 + Vite + Ant Design Vue 前端
  llm/              # LLM 客户端、工厂与 Provider
  mcp/              # MCP 协议与传输层
  messaging/        # RocketMQ 生产者与消息投递封装
  observability/    # 日志、Tracing、LangSmith
  persistence/      # 数据库模型与仓储
  prompt/           # Prompt 契约、仓库与模板
  rag/              # 知识库索引、检索与向量存储
  scripts/          # 本地开发和运维辅助脚本
  security/         # API Key、JWT 登录、访客额度、限流与安全治理
  server/           # 独立辅助服务源码
  sql/              # MySQL 与 pgvector 初始化脚本
  stream/           # SSE 编码与响应
  tests/            # 跨模块架构约束测试
```

## 快速启动

当前项目采用这套启动方式：

- Docker：只启动中间件，以及 RocketMQ 相关的两个后台任务容器。
- 本地进程：启动后端 API、前端、Celery Worker。
- 前后端不放进 Docker，MySQL / Redis / pgvector / Elasticsearch / MinIO / RocketMQ 统一由 Docker Compose 提供。

### 1. 准备 `.env`

复制 `.env.example` 为 `.env`，并填写真实密钥和 Docker 中间件密码。

```env
MYSQL_ROOT_PASSWORD=change-me
MYSQL_PASSWORD=change-me
REDIS_PASSWORD=change-me
PGVECTOR_PASSWORD=change-me

MYSQL_URL=mysql+pymysql://ai_love:change-me@127.0.0.1:3307/ai_love
MYSQL_URL_DOCKER=mysql+pymysql://ai_love:change-me@mysql:3306/ai_love
REDIS_URL=redis://:change-me@127.0.0.1:6380/0
VECTOR_DB_URL=postgresql+psycopg://ai_love:change-me@127.0.0.1:5433/ai_love_vector
```

说明：
- `MYSQL_URL` 是给本地 `uvicorn` / `celery` 进程用的，走宿主机映射端口 `3307`。
- `MYSQL_URL_DOCKER` 是给 Docker 里的 `memory-consumer` / `memory-outbox-relay` 用的，直接写容器服务名 `mysql:3306`。
- Redis 和 pgvector 也一样：本地进程走 `127.0.0.1:6380`、`127.0.0.1:5433`，容器内部走 `redis:6379`、`postgres:5432`。
- `GUEST_DAILY_MESSAGE_LIMIT` 才是匿名访客试用次数的运行时真值；`core/config.py` 里的数字只是默认兜底值。

### 2. 初始化 MySQL

首次启动 `mysql` 容器时会自动执行 [sql/mysql_init.sql](/c:/Users/33185/Desktop/ai-love/sql/mysql_init.sql:1)，创建用户、认证、会话、安全事件和 `memory_event_outbox` 表，无需再手动连本机 MySQL 初始化。

如果是在已有 MySQL 数据库上升级，需要重新执行 `sql/mysql_init.sql`，确保新增的 `auth_accounts`、`auth_refresh_tokens` 表已经存在。

### 3. 启动 Docker 中间件和 MQ 后台任务

```bash
docker compose up -d --build
```

Docker 当前只启动这些服务：

- `mysql / redis`：业务库与缓存
- `elasticsearch / kibana / elasticvue`：知识检索和可视化
- `postgres`：pgvector 向量库
- `minio`：文件对象存储
- `reranker-api`：RAG 重排服务
- `rocketmq-namesrv / rocketmq-broker / rocketmq-dashboard`：长期记忆事件队列
- `memory-consumer`：长期记忆 RocketMQ 消费者
- `memory-outbox-relay`：长期记忆失败补投任务

查看状态和日志：

```bash
docker compose ps
docker compose logs -f mysql
docker compose logs -f redis
docker compose logs -f memory-consumer
docker compose logs -f memory-outbox-relay
docker compose logs -f rocketmq-broker
```

常用入口：

- MySQL（宿主机）：`127.0.0.1:3307`
- Redis（宿主机）：`127.0.0.1:6380`
- pgvector/PostgreSQL（宿主机）：`127.0.0.1:5433`
- RocketMQ Dashboard：`http://127.0.0.1:8088`
- Kibana：`http://127.0.0.1:5601`
- Elasticvue：`http://127.0.0.1:8888`
- Elasticsearch API：`http://127.0.0.1:9200`
- MinIO Console：`http://127.0.0.1:9001`

### 4. 启动后端 API

Windows PowerShell：

```powershell
cd C:\Users\33185\Desktop\ai-love
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8081 --reload --loop core.event_loop:windows_compatible_loop_factory
```

健康检查：

```text
http://127.0.0.1:8081/health
```

### 5. 启动 Celery Worker

Celery Worker 不走 Docker，负责知识文件异步索引。

```powershell
cd C:\Users\33185\Desktop\ai-love
.\.venv\Scripts\celery.exe -A agents.worker.celery_app worker --loglevel=info --pool=solo
```

如果当前环境不用知识文件异步索引，可以在 `.env` 里关闭启动探针：

```env
CELERY_WORKER_PROBE_ENABLED=false
```

说明：
- 当前项目要求 LangGraph Checkpointer 必须可用，不再支持“无持久化降级”运行。
- Windows 本地启动后端时，必须带 `--loop core.event_loop:windows_compatible_loop_factory`，否则 psycopg 异步连接池和 PostgresSaver 会因 `ProactorEventLoop` 不兼容而启动失败。

### 6. 启动前端

```powershell
cd C:\Users\33185\Desktop\ai-love\frontend
npm install
npm run dev
```

前端默认访问本地后端：`http://127.0.0.1:8081`。

## 匿名访客试用额度排查

- `GUEST_DAILY_MESSAGE_LIMIT=1` 的语义是：第 1 条匿名消息允许发送，第 2 条开始返回 `LOGIN_REQUIRED`。
- 改完 `.env` 里的 `GUEST_DAILY_MESSAGE_LIMIT` 后，必须重启当前正在监听 `127.0.0.1:8081` 的后端进程，不能只改代码不重启。
- 如果机器上有多个 `8081` 监听进程，前端可能打到另一份旧实例。PowerShell 可用：

```powershell
netstat -ano | findstr :8081
Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -in @(替换成上面看到的PID) } | Select-Object ProcessId,Name,CommandLine
```

- 访客额度联调时可以直接看响应头：
  - `X-Guest-Identity`
  - `X-Guest-Limit`
  - `X-Guest-Remaining`
  - `X-Guest-Count`
  - `X-Guest-Quota-Reason`

- 后端启动日志会打印当前生效的 `guest_daily_message_limit` 和来源，便于确认是不是读到了 `.env`。

### 7. 高德 MCP（可选）

默认不启动高德 MCP。如果需要地图能力：

```env
MCP_AMAP_ENABLED=true
AMAP_MAPS_API_KEY=你的高德 Key
```

然后启动：

```bash
docker compose --profile amap up -d mcp-amap
```

不需要地图能力时保持 `MCP_AMAP_ENABLED=false`。

## 当前能力

- 后端按 `api / core / contracts / agents / rag / llm / persistence / security / messaging` 拆分。
- 暴露 `GET /health`、`POST /auth/register`、`POST /auth/login`、`POST /chat/stream`、`GET /chat/conversations`、知识库索引与检索接口。
- 支持未登录访客每日试用次数，超限返回 `LOGIN_REQUIRED`，登录后继续发送。
- 登录用户使用 JWT 认证，聊天、会话历史和长期记忆都以后端认证出的 `users.id` 为准。
- 保留 Redis 限流、会话持久化、长期记忆、LangGraph 工作流、MinIO 文件持久化能力。
- 前端已切换到新路由，可直接联调健康检查、登录弹窗与流式聊天链路。

## 长期记忆异步链路

长期记忆不在聊天主链路里直接提取和落库。流程是：

```text
聊天结束
  -> 生成 ai_love_memory_extraction 事件
  -> 投递 RocketMQ
  -> memory-consumer 消费事件
  -> 调用结构化模型判断是否保存
  -> 写入 pgvector
```

匿名访客只保留短期上下文和会话记录，不写入长期记忆。只有登录用户完成聊天后，才会把后端认证出的 `users.id` 写入长期记忆事件。

如果 RocketMQ 临时不可用，事件会先写入 MySQL 的 `memory_event_outbox`，由 `memory-outbox-relay` 循环补投。

- Topic：`ai_love_memory_extraction`
- Tag：`memory.extract.v1`
- Consumer Group：`ai_love_memory_consumer`
- Outbox 表：`memory_event_outbox`

一句话：现在是前后端、本地 Worker 继续本机跑；MySQL、Redis、pgvector、ES、MinIO、RocketMQ 和长期记忆后台任务统一走 Docker。
