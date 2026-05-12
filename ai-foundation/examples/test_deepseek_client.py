"""验证 DeepSeekClient 继承和多态。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.deepseek_impl import DeepSeekClient
from ai_foundation.llm.base import BaseLLMClient  # 多态验证用


async def main() -> None:
    config = LLMConfig()

    # 1. 实例化子类
    client: BaseLLMClient = DeepSeekClient(  # ← 类型标注为 BaseLLMClient
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
    )

    # 2. 调用父类提供的 chat() 方法（多态）
    response = await client.chat(
        user_message="用一句话解释什么是 Python 的 super()。",
        system_prompt="你是 Python 教学助手，用中文回答。",
    )

    print(f"模型: {response.model}")
    print(f"回复: {response.content}")
    print(f"Tokens: {response.tokens_used}")

    # 3. 验证多态：isinstance 检查
    print(f"\n是 DeepSeekClient 吗？ {isinstance(client, DeepSeekClient)}")
    print(f"是 BaseLLMClient 吗？ {isinstance(client, BaseLLMClient)}")


if __name__ == "__main__":
    asyncio.run(main())