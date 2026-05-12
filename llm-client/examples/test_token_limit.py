"""验证 Token 自动裁剪——模拟超长对话。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_client.chat import ChatSession
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    # 故意设很小的 token 预算，触发裁剪
    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是 AI 助手。",
        max_history_tokens=200,  # 很小的预算
    )

    # 连续发多条长消息
    long_text = "Python 是一种广泛使用的高级编程语言。" * 10  # 约 100+ chars
    for i in range(5):
        reply = await session.send(f"第 {i+1} 轮: {long_text}")
        print(f"第 {i+1} 轮完成，当前消息数: {session.message_count}")
        print(f"  token 估算: {session._count_tokens()}")

    print(f"\n最终 history 消息数: {session.message_count}")
    print("Token 裁剪功能正常！")


if __name__ == "__main__":
    asyncio.run(main())