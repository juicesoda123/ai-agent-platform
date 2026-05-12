# Day 11 — Function Calling：Agent 调用工具的底层机制

> Phase 2：LLM API 编程  |  预计用时：50 分钟  |  2026-05-05

---

## 今日目标

1. 理解 Function Calling 的原理——LLM 不会执行函数，它只是"说要调哪个函数"
2. 学会用 Pydantic 自动生成 JSON Schema
3. 实现一条完整的 Tool Calling 链路：定义工具 → 模型决策 → 执行工具 → 返回结果
4. 产出：一个能调计算器和搜索工具的 CLI

---

## 一、概念对齐：LLM 不执行函数

Function Calling 经常被误解。**LLM 永远不会执行你的代码**。它的流程是：

```
1. 你告诉模型："你有这些工具可以用：[计算器, 搜索]"
2. 用户问："3+5 等于几？"
3. 模型分析：这个问题需要用到"计算器"工具，参数是 expression="3+5"
4. 模型输出 JSON：{"tool": "calculator", "params": {"expression": "3+5"}}
                                    ↑
                          模型只负责到这里！
5. 你的代码取出 JSON，调用真正的 calculator("3+5")
6. 你的代码把结果 "8" 塞回 messages，再调一次模型
7. 模型拿到结果，生成最终回复："3+5 等于 8"
```

模型是**决策者**，不是**执行者**。它告诉你"用哪个工具、传什么参数"，你的代码负责执行。

---

## 二、动手实战（35 分钟）

### 任务 1：创建工具系统

在 `src/llm_client/` 下新建 `tools.py`：

```python
"""工具定义 + 工具执行器——Function Calling 完整链路。

教学点：
  1. Pydantic → JSON Schema：一个 model_json_schema() 搞定
  2. Tool 对象：把函数 + 元数据 + Schema 封装在一起
  3. 执行链路：模型选工具 → 解析参数 → 执行 → 返回结果
"""

import json
from typing import Callable
from pydantic import BaseModel, Field


# ——— 工具定义 ———
class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，如 '3 + 4 * 2'")


class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")


# ——— 工具包装 ———
class Tool:
    """一个工具 = 名字 + 描述 + 参数 Schema + 执行函数。"""

    def __init__(self, name: str, description: str, input_model: type[BaseModel], func: Callable):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.func = func

    def to_openai_schema(self) -> dict:
        """转成 OpenAI Function Calling 需要的格式。"""
        schema = self.input_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def run(self, args_json: str) -> str:
        """执行工具：JSON 参数 → 调函数 → 返回字符串结果。"""
        params = self.input_model.model_validate_json(args_json)
        return str(self.func(**params.model_dump()))


# ——— 具体的工具函数 ———
def calculator(expression: str) -> str:
    """安全的计算器——只做简单数学，不 eval 任意代码。"""
    allowed = set("0123456789+-*/().%^ ")
    if not all(c in allowed for c in expression):
        return "错误：表达式包含不安全字符"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"


def search(query: str) -> str:
    """模拟搜索——暂时返回假数据，Phase 3 接真正的搜索 API。"""
    return f"搜索结果（模拟）: 关于'{query}'，找到 3 条相关信息..."

```

### 任务 2：给 ChatSession 加上工具调用

在 `chat.py` 的 `ChatSession` 加一个新方法 `send_with_tools()`：

```python
async def send_with_tools(self, user_input: str, tools: list) -> str:
    """发送消息，允许模型调用工具。"""
    self.history.append({"role": "user", "content": user_input})
    self._trim_history()

    # 第一次调用：模型决定是否调工具
    response = await self.client.chat.completions.create(
        model=self.model,
        messages=self.history,
        tools=[t.to_openai_schema() for t in tools],
    )

    msg = response.choices[0].message

    # 如果模型要求调工具
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = tool_call.function.arguments

            # 找到对应工具并执行
            tool = next(t for t in tools if t.name == tool_name)
            result = tool.run(tool_args)

            # 把工具调用和结果加入历史
            self.history.append({
                "role": "assistant",
                "tool_calls": [{"id": tool_call.id, "type": "function",
                                "function": {"name": tool_name, "arguments": tool_args}}],
            })
            self.history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        # 第二次调用：模型根据工具结果生成最终回复
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
        )
        msg = response.choices[0].message

    reply = msg.content
    self.history.append({"role": "assistant", "content": reply})
    return reply
```

### 任务 3：验证脚本

在 `examples/` 下新建 `test_tool_calling.py`：

```python
"""验证 Function Calling——模型自动选择工具并执行。"""
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
        system_prompt="你是 AI 助手。如果用户问数学题，用 calculator。如果问实时信息，用 search。",
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
```

运行：

```bash
cd llm-client && python examples/test_tool_calling.py
```

---

## 三、验收标准

- 测试 1（数学题）→ 模型自动调 `calculator`，返回计算结果
- 测试 2（天气）→ 模型自动调 `search`，返回搜索结果（模拟）
- 测试 3（闲聊）→ 模型不调工具，直接回复

---

## 四、概念速查：Pydantic → JSON Schema 自动转换

```python
# 你定义
class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式")

# model_json_schema() 自动生成
{
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "数学表达式"
        }
    },
    "required": ["expression"]
}
```

这就是 D3 学的 Pydantic 在 Agent 里最核心的应用。你只需要定义 Pydantic 模型，JSON Schema 自动生成，不用手写。
