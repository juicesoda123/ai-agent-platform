import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.factory import create_llm_client
from ai_foundation.llm.base import BaseLLMClient

async def ask(client: BaseLLMClient, question: str) -> None:
    r = await client.chat(user_message=question)
    print(f"LLM 回复: {r.content} (模型: {r.model}, tokens 用量: {r.tokens_used})")

async def main() -> None:
    config = LLMConfig()
    client = create_llm_client(config)
    print(f"使用模型：{type(client).__name__}")

    questions = [
        "什么是 Python 装饰器？一句话。",
        "什么是设计模式中的工厂模式？一句话。",
    ]


    for q in questions:
        await ask(client, q)

        print(f"\nisinstance(client, BaseLLMClient): {isinstance(client, BaseLLMClient)}")  # True，说明工厂函数返回的对象是正确的类型

if __name__ == "__main__":
    asyncio.run(main())