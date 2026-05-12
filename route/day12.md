# Day 12 — 多模型统一接口 + CLI 对话机器人

> Phase 2：LLM API 编程  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 把 Phase 1 的工厂模式搬进 `llm-client`，统一 DeepSeek/OpenAI 入口
2. 把 ChatSession 的多轮/流式/工具调用整合成一个完整的 CLI
3. 产出：一个能切模型、带工具调用的命令行对话机器人

---

## 一、动手实战（30 分钟）

### 任务 1：创建统一入口 `llm_client/client.py`

```python
"""LLM 客户端工厂——一行代码选择模型。"""
import os
from openai import AsyncOpenAI


def create_client() -> AsyncOpenAI:
    """根据环境变量自动选择 DeepSeek 或 OpenAI。"""
    if os.getenv("DEEPSEEK_API_KEY"):
        return AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    elif os.getenv("OPENAI_API_KEY"):
        return AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://api.openai.com/v1",
        )
    raise ValueError("未找到 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
```

### 任务 2：完整 CLI 对话机器人

在 `examples/` 下新建 `cli_full.py`——整合流式 + 工具调用 + Token 管理：

```python
"""完整 CLI 对话机器人——流式 + 工具调用 + 多轮记忆。"""
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
        system_prompt="你是 AI 助手，可以用 calculator 算数学题，用 search 搜信息。中文回答。",
    )

    print("=" * 50)
    print("AI 对话机器人（流式 + 工具调用）")
    print(HELP_TEXT)

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/history":
            for i, msg in enumerate(session.history):
                content = msg.get("content", "")[:80]
                print(f"  [{msg['role']}] {content}")
            continue
        if user_input == "/tokens":
            print(f"  当前 token 数: {session._count_tokens()} / {session.max_history_tokens}")
            continue
        if user_input == "/tools":
            for t in TOOLS:
                print(f"  {t.name}: {t.description}")
            continue

        # 流式回复
        print("AI: ", end="", flush=True)
        async for chunk in session.send_stream(user_input):
            print(chunk, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
```

### 任务 3：给流式也加上工具调用

在 `chat.py` 里加 `send_stream_with_tools()`——流式 + 工具调用的组合：

```python
async def send_stream_with_tools(self, user_input: str, tools: list) -> AsyncGenerator[str, None]:
    """流式发送，同时支持工具调用。"""
    self.history.append({"role": "user", "content": user_input})
    self._trim_history()

    response = await self.client.chat.completions.create(
        model=self.model,
        messages=self.history,
        tools=[t.to_openai_schema() for t in tools],
    )

    msg = response.choices[0].message

    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = tool_call.function.arguments
            tool = next((t for t in tools if t.name == tool_name), None)
            result = tool.run(tool_args) if tool else f"错误：未找到 {tool_name}"

            print(f"\n  [调用工具: {tool_name}({tool_args}) → {result}]")

            self.history.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": tool_args},
                }],
            })
            self.history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        # 工具结果拿回来后，流式生成最终回复
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            stream=True,
        )
        full_reply = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                full_reply += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content
        self.history.append({"role": "assistant", "content": full_reply})
    else:
        # 没有工具调用，直接流式回复
        self.history.pop()  # 撤回刚加的 user 消息
        async for chunk in self.send_stream(user_input):
            yield chunk
```

---

## 二、验收标准

在 VS Code 终端跑：

```bash
cd llm-client && python examples/cli_full.py
```

测试三个场景：
1. 直接问 → 流式回复
2. "3 的 5 次方" → 自动调 calculator → 流式返回结果
3. `/tokens` → 显示 token 用量

全部通过 D12 就过了。

---

## 三、Phase 2 即将收尾

D7（明天）是 Phase 2 最后一战——三模型对比评测。D5 和 D6 今天合在一起搞定，你已经有全部材料：工厂模式（Phase 1）+ 流式（D9）+ Token（D10）+ 工具调用（D11），拼起来就是完整 CLI。
