"""自动化测试流式输出 + 多轮记忆。"""
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

    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是 AI 助手，用中文回答，不超过两句话。",
    )

    # 测试流式
    print("=== 流式输出测试 ===")
    chunks = []
    print("AI: ", end="", flush=True)
    async for chunk in session.send_stream("用一句话介绍 Python。"):
        chunks.append(chunk)
        print(chunk, end="", flush=True)
    print("\n")
    full_reply = "".join(chunks)
    print(f"收到 chunk 数: {len(chunks)}")
    print(f"完整回复长度: {len(full_reply)} 字符\n")

    # 验证多轮记忆：history 里 assistant content 不为空
    last_msg = session.history[-1]
    print(f"history 最后一条 role: {last_msg['role']}")
    print(f"history 最后一条 content 长度: {len(last_msg['content'])} 字符")

    if last_msg["role"] == "assistant" and len(last_msg["content"]) > 0:
        print(">>> 流式输出 + 记忆存储验证通过！")
    else:
        print(">>> 失败：assistant 回复未正确存入 history")


if __name__ == "__main__":
    asyncio.run(main())
