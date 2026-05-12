"""DeepSeek LLM 客户端 —— 继承 BaseLLMClient，对接 DeepSeek API。

教学点：
  1. 继承：DeepSeekClient(BaseLLMClient) 复用父类的 chat() 方法
  2. 多态：用 BaseLLMClient 类型接收，不关心底层是 DeepSeek 还是 OpenAI
  3. super()：调用父类的 __init__，让父类初始化通用属性
"""
import asyncio
from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from ai_foundation.llm.base import BaseLLMClient, LLMResponse, Message


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API 客户端。"""

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
                messages=message_dicts
                )
                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=self.model,
                    tokens_used=response.usage.total_tokens
                )
            except APIConnectionError as e:
                last_error = e
                print(f"连接错误，正在重试... ({attempt + 1}/{self.MAX_RETRIES})")
            except APIStatusError as e:
                if e.status_code < 500:
                    raise  # 客户端错误不重试
                last_error = e
                print(f"服务器错误{e.status_code}，正在重试... ({attempt + 1}/{self.MAX_RETRIES})")
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避

        raise last_error  # 最后一次重试失败，抛出异常  