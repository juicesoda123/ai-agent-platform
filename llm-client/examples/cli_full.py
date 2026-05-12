import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_client.chat import ChatSession
from llm_client.client import create_client 
from llm_client.tools import Tool, CalculatorInput, SearchInput, calculator, search
from dotenv import load_dotenv

load_dotenv()

TOOLS = [
    Tool(
        name="calculator",
        description="A simple calculator tool",
        input_schema=CalculatorInput,
        func=calculator,
    ),
    Tool(
        name="search",
        description="A simple search tool",
        input_schema=SearchInput,
        func=search,
    ),
]

HELP_TEXT = """
命令：
  /quit    — 退出
  /history — 查看对话历史
  /tokens  — 查看 token 用量
  /tools   — 列出可用工具
  其他内容  — 发送给 AI
"""

async def main() -> None:
    client = create_client()

    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是我的人工智能助手，可以使用工具来帮助我完成任务。",
    )

    print("=" * 50)
    print("AI 对话机器人（流式 + 工具调用）")
    print(HELP_TEXT)

    while True:
        user_input = input("你：").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            print("再见！")
            break
        if user_input == "/history":
            for msg in session.history:
                role = "我" if msg["role"] == "user" else "AI"
                print(f"{role}: {msg['content']}")
            continue
        if user_input == "/tokens":
            print(f"当前 tokens 数: {session._count_tokens()} / {session.max_history_tokens}")
            continue
        if user_input == "/tools":
            for t in TOOLS:
                print(f"- {t.name}: {t.description}")
            continue

        print("AI：", end="", flush=True)
        async for chunk in session.send_stream_with_tools(user_input, TOOLS):
            print(chunk, end="", flush=True)
        print()  # 换行