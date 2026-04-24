"""Embedding 服务：复用 xai_router 网关调用 OpenAI 兼容的 Embedding 接口。"""

from __future__ import annotations

import hashlib
import logging
import time
from threading import Lock

from openai import AsyncOpenAI

from core.config import get_settings

logger = logging.getLogger(__name__)

# 全局嵌入缓存（进程内 LRU，TTL 60 秒），避免同一 query 重复调用 API
_EMBED_CACHE: dict[str, tuple[list[float], float]] = {}
_CACHE_MX = Lock()
_CACHE_MAX_SIZE = 512  # 最多缓存 512 条嵌入向量
_CACHE_TTL_SECONDS = 60.0  # 缓存有效期 60 秒


def _get_cache_key(text: str) -> str:
    """计算文本的缓存 key，使用 SHA256 哈希避免存储大文本。
    
    目的：执行计算文本的缓存 key，使用 SHA256 哈希避免存储大文本相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _cache_get(key: str) -> list[float] | None:
    """从全局缓存读取嵌入向量，TTL 过期返回 None。
    
    目的：执行从全局缓存读取嵌入向量，TTL 过期返回 None相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    with _CACHE_MX:
        entry = _EMBED_CACHE.get(key)
        if entry is None:
            return None
        embedding, timestamp = entry
        if time.monotonic() - timestamp > _CACHE_TTL_SECONDS:
            _EMBED_CACHE.pop(key, None)
            return None
        return embedding


def _cache_set(key: str, embedding: list[float]) -> None:
    """写入全局缓存，超容量时清理最旧的 25% 条目。
    
    目的：执行写入全局缓存，超容量时清理最旧的 25% 条目相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    with _CACHE_MX:
        if len(_EMBED_CACHE) >= _CACHE_MAX_SIZE:
            # 按时间戳升序移除最旧的 25% 条目
            sorted_items = sorted(_EMBED_CACHE.items(), key=lambda x: x[1][1])
            for k, _ in sorted_items[: _CACHE_MAX_SIZE // 4]:
                _EMBED_CACHE.pop(k, None)
        _EMBED_CACHE[key] = (embedding, time.monotonic())


class EmbeddingService:
    """文本转向量服务，支持单条和批量嵌入。

    目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    def __init__(self) -> None:
        """初始化Embedding服务实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.llm_base_url,
        )

    async def embed_text(self, text: str) -> list[float]:
        """将单条文本转为向量。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        self._check_api_key()
        text = text.strip()
        if not text:
            # 空文本返回零向量，避免 API 报错
            return [0.0] * self.settings.vector_dimension

        cache_key = _get_cache_key(text)
        cached = _cache_get(cache_key)
        if cached is not None:
            logger.debug("Embedding 缓存命中: key=%s", cache_key)
            return cached

        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=text,
        )
        embedding = response.data[0].embedding
        _cache_set(cache_key, embedding)
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本转向量，按 ``embedding_batch_size`` 分批调用。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        if not texts:
            return []

        self._check_api_key()
        batch_size = self.settings.embedding_batch_size
        all_embeddings: list[list[float]] = []

        # 记录空文本的位置，跳过 API 调用并用零向量填充
        zero_vec = [0.0] * self.settings.vector_dimension

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            # 筛出非空文本做实际 API 调用
            non_empty_indices: list[int] = []
            non_empty_texts: list[str] = []
            for i, t in enumerate(batch):
                stripped = t.strip()
                if stripped:
                    non_empty_indices.append(i)
                    non_empty_texts.append(stripped)

            # 初始化本批结果为零向量
            batch_embeddings: list[list[float]] = [list(zero_vec) for _ in batch]

            if non_empty_texts:
                response = await self.client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=non_empty_texts,
                )
                # OpenAI 返回的 data 按 index 排序，但为安全起见按 index 映射
                sorted_data = sorted(response.data, key=lambda d: d.index)
                for j, item in enumerate(sorted_data):
                    original_idx = non_empty_indices[j]
                    batch_embeddings[original_idx] = item.embedding

            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _check_api_key(self) -> None:
        """检查 API Key 是否配置，未配置时抛出 RuntimeError。

        目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        if not self.settings.xai_api_key:
            raise RuntimeError(
                "未配置 XAI_API_KEY，无法调用 Embedding 模型。请在 .env 中设置 XAI_API_KEY。"
            )
