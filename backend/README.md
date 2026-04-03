# Backend

基于 `FastAPI + Pydantic v2 + LangGraph` 的后端骨架，当前提供：

- 配置管理
- 健康检查
- 最小聊天链路
- Agent / Memory / RAG / Safety 目录预留

## 启动

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
