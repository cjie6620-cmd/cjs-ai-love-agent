from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from ...core.config import get_settings


class LlmClient:
    """统一封装 OpenAI 兼容接口，方便后续替换不同网关或模型供应商。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.llm_base_url,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.xai_api_key:
            raise RuntimeError("未配置 XAI_API_KEY，无法调用真实模型。")

        completion = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return completion.choices[0].message.content or ""

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        if not self.settings.xai_api_key:
            raise RuntimeError("未配置 XAI_API_KEY，无法调用真实模型。")

        stream = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
