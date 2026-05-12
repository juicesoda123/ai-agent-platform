"""OpenAI LLM 客户端 —— 和 DeepSeekClient 共用同一个父类。"""

import asyncio
from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from ai_foundation.llm.base import BaseLLMClient, LLMResponse, Message


class OpenAIClient(BaseLLMClient):
    """OpenAI API 客户端。代码结构和 DeepSeekClient 几乎一样。"""

    MAX_RETRIES = 3

    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        super().__init__(model, api_key, base_url)
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def _complete(self, messages: list[Message]) -> LLMResponse:
        message_dicts = [msg.to_dict() for msg in messages]
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=message_dicts,
                )
                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=self.model,
                    tokens_used=response.usage.total_tokens,
                )
            except APIConnectionError as e:
                last_error = e
                print(f"  [OpenAI 网络错误] 重试 {attempt+1}/{self.MAX_RETRIES}")
            except APIStatusError as e:
                if e.status_code < 500:
                    raise
                last_error = e
                print(f"  [OpenAI {e.status_code}] 重试 {attempt+1}/{self.MAX_RETRIES}")

            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)

        raise last_error