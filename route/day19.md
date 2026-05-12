# Day 19 — ReAct Agent：Think → Act → Observe 循环

> Phase 4：单 Agent 开发  |  预计用时：50 分钟  |  2026-05-05

---

## 今日目标

1. 理解 ReAct 范式——Reason + Act，想了做，做了反思
2. 实现 Agent 的核心循环：Thought → Action → Observation → 循环
3. 把 RAG 和 Calculator 注册为 Agent 的工具
4. 产出：`ReActAgent` — 能自主决定"搜知识库"还是"直接回答"

---

## 一、概念对齐：ReAct 是什么

```
用户: "RAG 是什么？它的数学原理中 3^5 等于多少？"

Agent 循环:
  Thought: 这个问题有两部分——RAG 概念和数学计算。先搜知识库。
  Action: search_rag("RAG 是什么")
  Observation: RAG 是检索增强生成技术...

  Thought: RAG 概念已查到。现在需要算 3^5。
  Action: calculator("3^5")
  Observation: 243

  Thought: 两部分答案都有了，可以回复用户了。
  Answer: RAG 是检索增强生成技术...3^5 = 243。
```

**关键**：Agent 不是一口气回答——它**一步一步想**、**调工具**、**看结果**、**再决定下一步**。

---

## 二、动手实战（35 分钟）

### 任务 1：创建 `agent.py`

在 `AI-Agent/` 下新建 `single-agent/` 项目：

```
single-agent/
├── .env              ← 复制 rag-system/.env
├── .gitignore
├── src/agent/
│   ├── __init__.py
│   └── react_agent.py  ← 今天写
└── examples/
    └── test_agent.py   ← 今天写
```

**`src/agent/react_agent.py`**：

```python
"""ReAct Agent —— Think → Act → Observe 循环。

教学点：
  1. ReAct 范式：不是一步回答，是 Thought → Action → Observation 循环
  2. Agent 自主决策：每次循环自己决定"调工具"还是"给出最终答案"
  3. System Prompt 驱动：整个循环靠 Prompt 约束行为
"""

import json
import re
from openai import AsyncOpenAI


SYSTEM_PROMPT = """你是一个自主 Agent，可以调用工具来回答问题。你必须严格按照以下格式响应：

当需要调用工具时：
Thought: [你对当前情况的思考]
Action: [工具名称]
Action Input: [JSON 格式的工具参数]

当有足够信息回答用户时：
Thought: [你的最终思考]
Final Answer: [用中文回答用户的问题]

可用工具：
- calculator: 执行数学计算。参数：{"expression": "数学表达式"}
- search_rag: 搜索知识库。参数：{"query": "搜索关键词"}

规则：
1. 每次只能调用一个工具
2. 工具结果会以 Observation 形式返回给你
3. 拿到足够信息后立即给出 Final Answer
4. 不要编造信息，工具没返回就说不知道
"""


class ReActAgent:
    """ReAct 自主 Agent。"""

    def __init__(self, client: AsyncOpenAI, model: str = "deepseek-chat"):
        self.client = client
        self.model = model
        self.tools: dict = {}  # name → function

    def register_tool(self, name: str, func) -> None:
        """注册工具。func 接收 dict 参数，返回 str。"""
        self.tools[name] = func

    async def run(self, user_input: str, max_steps: int = 5) -> str:
        """运行 Agent，最多 max_steps 轮循环。"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]

        for step in range(max_steps):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})

            print(f"\n--- Step {step+1} ---")
            print(reply)

            # 检查是否给出了最终答案
            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply

            # 解析 Action
            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*?\})", reply, re.DOTALL)

            if not action_match:
                messages.append({"role": "user", "content": "请按格式输出：Thought/Action/Action Input 或 Final Answer"})
                continue

            tool_name = action_match.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}

            if tool_name not in self.tools:
                observation = f"工具 '{tool_name}' 不存在。可用工具：{list(self.tools.keys())}"
            else:
                try:
                    result = self.tools[tool_name](**tool_args)
                    observation = str(result)
                except Exception as e:
                    observation = f"工具执行错误: {e}"

            print(f"Observation: {observation}")
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        return "Agent 达到最大步数限制，未能给出最终答案。"
```

### 任务 2：验证脚本

**`examples/test_agent.py`**：

```python
"""验证 ReAct Agent —— 自动调用工具。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.react_agent import ReActAgent
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# 简单的工具函数
def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/().%^ ")
    if not all(c in allowed for c in expression):
        return "表达式包含不安全字符"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"

def search_rag(query: str) -> str:
    return f"关于'{query}'的搜索结果：RAG是检索增强生成技术，结合信息检索和LLM生成..."

async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    agent = ReActAgent(client)
    agent.register_tool("calculator", calculator)
    agent.register_tool("search_rag", search_rag)

    # 测试 1：需要计算器
    print("\n" + "="*60)
    answer = await agent.run("3 的 5 次方加上 100 等于多少？")
    print(f"\n>>> 最终答案: {answer}")

    # 测试 2：需要搜索
    print("\n" + "="*60)
    answer = await agent.run("什么是 RAG 技术？")
    print(f"\n>>> 最终答案: {answer}")

    # 测试 3：不需要工具
    print("\n" + "="*60)
    answer = await agent.run("你好，用一句话介绍你自己。")
    print(f"\n>>> 最终答案: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
cd single-agent && python examples/test_agent.py
```

---

## 三、验收标准

- "3 的 5 次方 + 100" → Agent 自动调 `calculator`，返回正确结果
- "什么是 RAG" → Agent 自动调 `search_rag`，返回搜索结果
- "你好" → Agent 不调工具，直接 Final Answer

---

## 四、概念速查：ReAct vs 普通 LLM 调用

| | 普通 LLM | ReAct Agent |
|------|---------|------------|
| 回答方式 | 一步到位 | 多步循环 |
| 工具调用 | 手动（Function Calling） | 自动（自己决定什么时候调） |
| 自我纠正 | 不会 | 看到 Observation 不对可以重试 |
| 适用场景 | 简单对话 | 复杂任务需要多步推理 |
