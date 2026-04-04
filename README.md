# AI Love Agent

面向情感陪伴、恋爱沟通、风格复刻、长期记忆与安全治理的企业级 AI Agent 工程骨架。

## 项目结构

```text
ai-love/
  backend/   # FastAPI 后端、Agent 编排、业务模块
  frontend/  # Vue3 + Vite + Ant Design Vue 前端
  docs/      # 设计说明与补充文档
```

## 快速启动

### 1. 启动基础设施

```bash
docker compose up -d
```

### 2. 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 当前能力

- 提供企业级目录骨架，便于后续扩展 Agent、RAG、记忆与安全治理模块。
- 后端内置健康检查与最小聊天接口，方便前后端联调。
- 数据库初始化改为手动执行 SQL 脚本，避免服务启动阶段自动建表。
- 前端内置工作台页面，可直接调用后端接口验证链路。

## 说明

- 当前提交是“项目基础盘”，重点解决分层、规范与联调路径，不包含完整业务实现。
- Prompt、记忆、RAG、安全等模块已预留独立目录，后续可以按业务逐步填充。
