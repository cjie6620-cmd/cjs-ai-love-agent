# -*- coding: utf-8 -*-
"""pytest 配置文件 - 全局测试夹具和配置。

目的：为测试套件提供全局测试夹具（Fixtures），如模拟的 Redis 服务、LLM 客户端等。
结果：测试环境配置完成，各测试模块可复用这些夹具。

Author: AI-Love Team
Version: 0.2.0
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# =============================================================================
# 项目路径配置
# =============================================================================
# 目的：将项目根目录添加到 Python 路径，确保测试可以导入项目模块
# 结果：无论从哪个目录运行 pytest，都能正确导入项目代码

# 计算项目根目录的绝对路径
PROJECT_ROOT = Path(__file__).resolve().parent

# 将项目根目录添加到 sys.path 的首位，确保优先使用项目中的模块
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 获取当前模块的日志记录器
logger = logging.getLogger(__name__)

# =============================================================================
# 全局测试夹具定义
# =============================================================================


@pytest.fixture(scope="function")
def redis_service():
    """提供模拟的 Redis 服务夹具。

    目的：模拟 Redis 服务的行为，用于测试依赖 Redis 的功能。
    作用域：函数级 - 每个测试函数都会创建新的实例。
    结果：返回 MagicMock 对象，模拟 RedisService 的所有方法。
    """
    logger.debug("创建模拟 Redis 服务夹具")
    mock_redis = MagicMock()
    mock_redis.check_rate_limit.return_value = True
    return mock_redis


@pytest.fixture(scope="function")
def mock_llm_client():
    """提供模拟的 LLM（大语言模型）客户端夹具。

    目的：模拟 LLM API 调用，避免在测试中产生真实 API 请求。
    作用域：函数级 - 每个测试函数都会创建新的模拟实例。
    结果：返回 MagicMock 对象，模拟 LLMClient 的响应行为。
    """
    logger.debug("创建模拟 LLM 客户端夹具")
    mock_client = MagicMock()
    mock_client.chat.return_value = "这是来自模拟 LLM 的回复"
    mock_client.stream_chat.return_value = iter(["模拟", "流式", "响应"])
    return mock_client


@pytest.fixture(scope="function")
def mock_rag_service():
    """提供模拟的 RAG（检索增强生成）服务夹具。

    目的：模拟 RAG 服务的检索功能，用于测试知识库相关功能。
    作用域：函数级 - 每个测试函数都会创建新的模拟实例。
    结果：返回 MagicMock 对象，模拟 RagService 的方法。
    """
    logger.debug("创建模拟 RAG 服务夹具")
    mock_service = MagicMock()
    mock_service.search.return_value = []
    mock_service.index_file.return_value = {"indexed": 0}
    return mock_service


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境会话级配置。

    目的：在整个测试会话开始前执行一次性设置。
    作用域：会话级 - 整个测试过程只执行一次。
    自动使用：autouse=True 表示无需在测试中显式导入。
    结果：测试环境配置完成并记录日志。
    """
    logger.info("=" * 60)
    logger.info("测试环境初始化开始")
    logger.info("=" * 60)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    yield

    logger.info("=" * 60)
    logger.info("测试环境清理完成")
    logger.info("=" * 60)
