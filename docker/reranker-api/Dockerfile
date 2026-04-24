FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY docker/reranker-api/requirements.txt /tmp/requirements.txt
# 运行环境配置为 CPU，先安装 CPU-only PyTorch，避免拉取巨大的 CUDA 依赖导致镜像构建失败
RUN pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY docker/reranker-api/app.py /app/app.py

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
