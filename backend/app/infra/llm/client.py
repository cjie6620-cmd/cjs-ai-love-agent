import asyncio

from openai import OpenAI

from ...core.config import get_settings


class LlmClient:
    """统一封装 OpenAI 兼容接口，方便后续替换不同网关或模型供应商。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(
            api_key=self.settings.xai_api_key,
            base_url=self.settings.llm_base_url,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.xai_api_key:
            raise RuntimeError("未配置 XAI_API_KEY，无法调用真实模型。")

        # OpenAI 官方 SDK 的同步客户端更通用，这里放到线程里执行，避免阻塞异步接口。
        return await asyncio.to_thread(self._generate_sync, system_prompt, user_prompt)

    def _generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return completion.choices[0].message.content or ""
