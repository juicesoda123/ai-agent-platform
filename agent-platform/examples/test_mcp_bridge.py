"""验证 Agent + MCP 文件工具集成 —— 需要 DeepSeek API Key。"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "single-agent" / "src"))

from openai import AsyncOpenAI
from agent.tool_register import ToolRegistry
from agent_platform.mcp_bridge import MCPBridge

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


async def main():
    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    # 1. 连接 MCP Filesystem Server
    npx = r"C:\Program Files\nodejs\npx.cmd"
    project = r"D:/大数据开发学习路线/AI-Agent"
    bridge = MCPBridge([npx, "-y", "@modelcontextprotocol/server-filesystem", project])

    # 2. 注入到 ToolRegistry
    registry = ToolRegistry()
    bridge.register_all(registry)

    tools = registry.list_tools()
    print(f"=== Agent 可用工具 ({len(tools)}) ===")
    for t in tools:
        print(f"  [{t['name']}] {t['description'][:60]}")

    # 3. Agent 调 LLM 读学习笔记
    system_prompt = registry.generate_system_prompt(
        "你是知识助手。用工具搜索/读取项目中的学习笔记，然后给出中文回答。"
        "\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [中文回答]"
    )

    question = "在这个项目的学习笔记里搜索一下，MCP协议的核心原理是什么？先列出route目录下有哪些文件，然后读相关的文档。"
    print(f"\nQ: {question}\n")

    import re, json

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    for cycle in range(5):
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
        )
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        print(f"[Cycle {cycle+1}] {reply[:300]}\n")

        if "Final Answer:" in reply:
            match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
            print(f"=== 最终回答 ===\n{match.group(1).strip() if match else reply}")
            break

        action = re.search(r"Action:\s*(\w+)", reply)
        input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)
        if action:
            tool_name = action.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}
            print(f"  → 调用 {tool_name}({tool_args})")
            observation = registry.call(tool_name, **tool_args)
            print(f"  ← 结果: {observation[:300]}\n")
            messages.append({"role": "user", "content": f"Observation: {observation[:1500]}"})
        else:
            break

    bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
