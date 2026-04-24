# AI Love Agent

面向情感陪伴、恋爱沟通、风格复刻、长期记忆与安全治理的企业级 AI Agent 工程骨架。

## 项目结构

```text
ai-love/
  app.py            # FastAPI 应用装配入口
  api/              # 路由与依赖
  core/             # 配置与容器装配
  contracts/        # 共享请求/响应契约
  llm/              # LLM 客户端、工厂与 Provider
  prompt/           # Prompt 契约、仓库与模板
  rag/              # 知识库索引、检索与向量存储
  agents/           # Agent 服务、工作流、记忆与工具
  persistence/      # 数据库模型与仓储
  security/         # API Key、限流与安全治理
  observability/    # 日志、Tracing、LangSmith
  mcp/              # MCP 协议与传输层
  stream/           # SSE 编码与响应
  frontend/         # Vue3 + Vite + Ant Design Vue 前端
  docs/             # 设计说明与补充文档
  sql/              # SQL 脚本
```

## 快速启动

### 1. 启动基础设施

```bash
docker compose up -d
```

说明：
- `docker-compose.yml` 启动 Elasticsearch、Kibana、Elasticvue、pgvector、MinIO、reranker，以及可选的高德 MCP 服务。
- MySQL 和 Redis 不在本项目 Docker 编排内，后端通过根目录 `.env` 中的 `MYSQL_URL`、`REDIS_URL` 连接你的本地或云端实例。
- 仓库只保留占位密码，真实密码只写入本地 `.env`，不要提交。

本地可视化入口：

- Kibana：`http://127.0.0.1:5601`，登录账号 `elastic`，密码为 `.env` 中的 `ES_PASSWORD`，默认占位值是 `change-me`。
- Elasticvue：`http://127.0.0.1:8888`，新建连接时 ES 地址填 `http://127.0.0.1:9200`，认证选择 basic auth，账号 `elastic`，密码为 `.env` 中的 `ES_PASSWORD`。
- Elasticsearch API：`http://127.0.0.1:9200`，可用 `/_cat/indices?v` 快速查看索引。
- MinIO Console：`http://127.0.0.1:9001`，账号为 `.env` 中的 `MINIO_ACCESS_KEY`，默认 `minioadmin`；密码为 `MINIO_SECRET_KEY`，默认占位值是 `change-me`。

### 2. 初始化数据库

项目不会在运行时自动创建 pgvector 业务表，首次启动前请手工执行 SQL：

```bash
psql -U postgres -d postgres -f sql/pgvector_init.sql
psql -U ai_love -d ai_love_vector -f sql/pgvector_schema.sql
```

执行顺序：

- `postgres` 库执行 `sql/pgvector_init.sql`
- `ai_love_vector` 库执行 `sql/pgvector_schema.sql`

### 3. 启动后端

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload

# 方式1：直接运行 Python 文件
python app.py

# 方式2：使用 uvicorn 命令行（推荐）
uvicorn app:app --host 127.0.0.1 --port 8000

# 方式3：带热重载的开发模式
uvicorn app:app --reload --host 127.0.0.1 --port 8000

# 方式4：多 workers（生产环境）
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000

```

后端启动前，先确认根目录 `.env` 已配置 LangSmith：

```env
LANGSMITH_ENABLED=true
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=你的 LangSmith API Key
LANGSMITH_PROJECT=project-ai
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_SAMPLE_RATE=1.0
LANGSMITH_PRIVACY_MODE=true
```

说明：
- 实际运行读取的是根目录 `.env`
- `app.py` 启动时会自动把这些变量同步到进程环境变量，LangGraph 和 LangSmith SDK 会直接读取
- 如果你只想本地跑功能、不上报链路，把 `LANGSMITH_ENABLED=false` 或 `LANGSMITH_TRACING=false` 即可
- `LANGSMITH_PRIVACY_MODE=true` 表示隐私模式：隐藏输入输出，并对 trace 做脱敏
- `LANGSMITH_PRIVACY_MODE=false` 表示调试模式：LangSmith Waterfall 可查看每个 workflow / tool / LLM 节点的原始输入输出

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 5. 配置高德 MCP（可选）

当 `.env` 中配置了 `MCP_AMAP_ENABLED=true` 时，需要准备一个支持 Streamable HTTP 的高德 MCP 服务。

`AMAP_MAPS_API_KEY` 不是项目内置的，需要你自己去高德开放平台申请：

- 申请地址：https://lbs.amap.com/
- 注册并创建应用后，在控制台获取 Web Service 对应的 Key

如果你已经在根目录 `.env` 中配置了：

```env
MCP_TRANSPORT=streamable_http
AMAP_MAPS_API_KEY=你的高德 Key
AMAP_MCP_URL=http://127.0.0.1:3100/mcp
AMAP_MCP_HEADERS_JSON=
MCP_AMAP_ENABLED=true
```

那后端就会通过 `AMAP_MCP_URL` 连接 Streamable HTTP MCP 服务。

如果你使用项目内置的高德 MCP 服务，需要单独启动 `amap` profile：

```bash
docker compose --profile amap up -d mcp-amap
```

说明：
- `AMAP_MCP_URL` 可以是本地地址，也可以是远端服务地址
- `AMAP_MCP_HEADERS_JSON` 用于补充认证头或网关头，格式为 JSON 对象
- README 不会写死真实秘钥，实际值请填写你自己申请的 `AMAP_MAPS_API_KEY`
- 如果不需要地图能力，把 `MCP_AMAP_ENABLED=false` 即可，不必启动这个服务

## 当前能力

- 提供根目录级后端骨架，核心模块按 `api / core / contracts / agents / rag / llm / persistence` 拆分。
- 暴露 `GET /health`、`POST /chat/reply`、`POST /chat/stream`、`GET /chat/conversations`、知识库索引与检索接口。
- 保留 Redis 限流、会话持久化、长期记忆、LangGraph 工作流、MinIO 文件持久化能力。
- 前端已切换到新路由，可直接联调健康检查与流式聊天链路。

## 说明

- `.env.example` 为根目录统一环境变量模板，实际运行时读取根目录 `.env`。
- 项目只保留根目录新骨架，不再提供旧后端兼容入口或兼容路由。

## 长期记忆 RocketMQ 异步落库

长期记忆不在聊天主链路里直接提取和落库。聊天结束后会生成 `ai_love_memory_extraction` 事件，优先投递 RocketMQ；如果 RocketMQ 临时不可用，事件会写入 MySQL 的 `memory_event_outbox`，后续补投。

### 基础设施

```bash
docker compose up -d rocketmq-namesrv rocketmq-broker rocketmq-dashboard
```

- RocketMQ Dashboard：http://127.0.0.1:8088
- Topic：`ai_love_memory_extraction`
- Tag：`memory.extract.v1`
- Consumer Group：`ai_love_memory_consumer`
- Redis 仍使用远程服务器，不在 `docker-compose.yml` 中启动。

### 数据库初始化

项目不会运行时自动建表，首次部署需要手工执行：

```bash
mysql -u root -p < sql/mysql_init.sql
```

`sql/mysql_init.sql` 中包含 `memory_event_outbox`，用于 RocketMQ 投递失败补偿。

### 启动消费者和补投

```bash
python -m agents.memory_consumer
python -m agents.memory_outbox_relay
```

消费者使用 DeepSeek 低成本结构化模型抽取 `MemoryDecision`，再调用长期记忆治理逻辑写入 pgvector。消费失败交给 RocketMQ 重试，超过最大次数进入 DLQ；业务侧用 `task_id` 做幂等，避免重复落库。
