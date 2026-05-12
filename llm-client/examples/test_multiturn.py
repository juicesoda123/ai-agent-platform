"""自动化多轮对话测试——验证模型能否记住上下文。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src/llm_client"))

from chat import ChatSession
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是 Python 学习助手，用中文回答，不超过两句话。",
    )

    # 第 1 轮
    r1 = await session.send("我叫小明，正在学 Python。")
    print(f"[第 1 轮] 用户: 我叫小明，正在学 Python。")
    print(f"[第 1 轮] AI: {r1}")
    print(f"[第 1 轮] 消息数: {session.message_count}\n")

    # 第 2 轮：测试记忆
    r2 = await session.send("我叫什么名字？")
    print(f"[第 2 轮] 用户: 我叫什么名字？")
    print(f"[第 2 轮] AI: {r2}")
    print(f"[第 2 轮] 消息数: {session.message_count}\n")

    # 验证：模型是否记住了名字
    if "小明" in r2:
        print(">>> 多轮记忆验证通过！模型记住了用户名字。")
    else:
        print(">>> 注意：模型可能没有记住名字，检查 messages 是否正确回传。")


if __name__ == "__main__":
    asyncio.run(main())
