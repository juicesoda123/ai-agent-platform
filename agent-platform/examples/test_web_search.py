"""验证 Agent + 联网搜索 —— 需要 DeepSeek API Key。"""
import asyncio
import sys
import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "single-agent" / "src"))

from openai import AsyncOpenAI
from agent.tool_register import ToolRegistry
from agent_platform.web_search import web_search, web_search_news
from pydantic import BaseModel, Field

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5, description="返回结果数量")


async def main():
    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    # 注册工具
    registry = ToolRegistry()
    registry.register("web_search", "搜索互联网，获取最新信息", web_search, SearchInput)
    registry.register("web_search_news", "搜索新闻，获取时效性信息", web_search_news, SearchInput)

    # 让 Agent 回答一个需要联网的问题
    system_prompt = registry.generate_system_prompt(
        "你是联网知识助手。可以用 web_search 搜索互联网获取最新信息。"
        "\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [中文回答]"
    )

    question = "搜索一下LangGraph是什么，它和LangChain有什么区别？用中文回答"
    print(f"Q: {question}\n")

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
            final = match.group(1).strip() if match else reply
            print(f"=== 最终回答 ===\n{final}")
            break

        action = re.search(r"Action:\s*(\w+)", reply)
        input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)
        if action:
            tool_name = action.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}
            print(f"  → {tool_name}({tool_args})")
            observation = registry.call(tool_name, **tool_args)
            print(f"  ← {observation[:400]}\n")
            messages.append({"role": "user", "content": f"Observation:\n{observation}"})


if __name__ == "__main__":
    asyncio.run(main())
