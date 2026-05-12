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
        system_prompt="你是我的 AI 助手，帮我解答问题。",
    )

    print("多轮对话 CLI（输入 /quit 退出，/history 看历史）\n")

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            print("退出对话。")
            break
        if user_input == "/history":
            print("\n对话历史:")
            for i, msg in enumerate(session.history):
                print(f"  {i+1}. {msg['role']}: {msg['content']}")
                continue
        reply = await session.send(user_input)
        print(f"AI: {reply}\n")
    
if __name__ == "__main__":
    asyncio.run(main())