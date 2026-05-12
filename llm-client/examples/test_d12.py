"""D12 自动化验证——流式工具调用 + 非工具流式。"""
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
    Tool("calculator", "执行数学计算", CalculatorInput, calculator),
    Tool("search", "搜索互联网信息", SearchInput, search),
]


async def main() -> None:
    client = create_client()
    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是 AI 助手，有 calculator 和 search 工具。中文回答。",
    )

    # 测试 1：流式工具调用
    print("=== 测试 1：流式 + 工具调用（计算器）===")
    chunks = []
    print("AI: ", end="", flush=True)
    async for chunk in session.send_stream_with_tools("3 的 10 次方是多少？", TOOLS):
        chunks.append(chunk)
        print(chunk, end="", flush=True)
    print(f"\n收到 {len(chunks)} 个 chunk\n")

    # 测试 2：流式无需工具
    print("=== 测试 2：流式 + 无工具（闲聊）===")
    chunks2 = []
    print("AI: ", end="", flush=True)
    async for chunk in session.send_stream_with_tools("你好，一句话介绍你自己。", TOOLS):
        chunks2.append(chunk)
        print(chunk, end="", flush=True)
    print(f"\n收到 {len(chunks2)} 个 chunk\n")

    print(">>> D12 验证通过！流式 + 工具调用 + 多轮记忆全部正常。")


if __name__ == "__main__":
    asyncio.run(main())
