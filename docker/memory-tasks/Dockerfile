FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LD_LIBRARY_PATH=/usr/local/lib:/usr/lib:${LD_LIBRARY_PATH}

WORKDIR /app

ARG ROCKETMQ_CPP_DEB_URL=https://github.com/apache/rocketmq-client-cpp/releases/download/2.0.0/rocketmq-client-cpp-2.0.0.amd64.deb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        gcc \
        libssl-dev \
        libffi-dev \
        libstdc++6 \
    && curl -fsSL "$ROCKETMQ_CPP_DEB_URL" -o /tmp/rocketmq-client-cpp.deb \
    && dpkg -i /tmp/rocketmq-client-cpp.deb \
    && rm -f /tmp/rocketmq-client-cpp.deb \
    && ldconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY agents ./agents
COPY contracts ./contracts
COPY core ./core
COPY llm ./llm
COPY messaging ./messaging
COPY observability ./observability
COPY persistence ./persistence
COPY prompt ./prompt
COPY rag ./rag
COPY security ./security
COPY stream ./stream
COPY mcp ./mcp

CMD ["python", "-m", "agents.memory_consumer"]
