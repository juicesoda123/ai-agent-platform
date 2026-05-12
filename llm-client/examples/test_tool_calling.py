import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_client.chat import ChatSession
from llm_client.tools import Tool, CalculatorInput, SearchInput, calculator, search
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    tools = [
        Tool("calculator", "执行数学计算", CalculatorInput, calculator),
        Tool("search", "搜索互联网信息", SearchInput, search),
    ]

    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是我的 AI 助手，帮我解答问题。你可以调用工具：calculator 和 search。",
    )

    # 测试 1：触发计算器
    print("=== 测试 1：计算器 ===")
    r1 = await session.send_with_tools("3 的 5 次方是多少？", tools)
    print(f"回复: {r1}\n")

    # 测试 2：触发搜索
    print("=== 测试 2：搜索 ===")
    r2 = await session.send_with_tools("今天北京的天气怎么样？", tools)
    print(f"回复: {r2}\n")

    # 测试 3：不需要工具
    print("=== 测试 3：闲聊 ===")
    r3 = await session.send_with_tools("你好，用一句话介绍你自己。", tools)
    print(f"回复: {r3}\n")


if __name__ == "__main__":
    asyncio.run(main())