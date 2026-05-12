# Day 23 — Multi-Agent 协作：Researcher + Coder + Reviewer

> Phase 5：Multi-Agent + MCP  |  预计用时：50 分钟  |  2026-05-05

---

## 今日目标

1. 理解多 Agent 协作的本质——每个 Agent 是专才，组合起来是通才
2. 实现三个角色 Agent：Researcher（搜索）、Coder（写代码）、Reviewer（审查）
3. 实现 Supervisor 调度——把任务分给对的 Agent
4. 产出：`multi-agent/` 项目，三个 Agent 协作完成一个任务

---

## 一、概念对齐：多 Agent 架构

```
用户: "写一个函数判断质数，并搜索质数的应用"

         ┌─────────────┐
         │  Supervisor  │ ← 分析任务，分发给专才
         └──┬──┬──┬────┘
            │  │  │
    ┌───────┘  │  └──────────┐
    ↓          ↓             ↓
Researcher   Coder       Reviewer
"搜索质数    "写质数判    "检查代码
  应用"      断函数"      正确性"
    ↓          ↓             ↓
    └──────────┴─────────────┘
                ↓
           最终交付
```

**和 Plan-and-Execute 的区别**：PlanAgent 是**一个 Agent 多步执行**，Multi-Agent 是**多个 Agent 并行/串行协作**。

---

## 二、动手实战（35 分钟）

### 任务 1：建 `multi-agent/` 项目

```
multi-agent/
├── .env                  ← 复制
├── .gitignore
├── src/multi_agent/
│   ├── __init__.py
│   ├── base.py           ← 基础 Agent 类
│   └── supervisor.py     ← Supervisor 调度器
└── examples/
    └── test_team.py      ← 验证脚本
```

### 任务 2：`src/multi_agent/base.py`

```python
"""Base Agent —— 所有角色 Agent 的基类。"""

import re, json
from openai import AsyncOpenAI


class BaseAgent:
    """通用 Agent：有名字、有角色、有工具。"""

    def __init__(
        self,
        name: str,
        role: str,
        client: AsyncOpenAI,
        registry,
    ):
        self.name = name
        self.role = role
        self.client = client
        self.registry = registry

    async def execute(self, task: str, max_cycles: int = 3) -> str:
        """执行一个子任务，返回结果。"""
        system_prompt = f"""你是 {self.name}，角色是 {self.role}。

{self.registry.generate_system_prompt("你可以使用以下工具：")}

严格按格式：
Action: [工具名]
Action Input: [JSON参数]

或任务完成时：
Final Answer: [你的交付]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        for _ in range(max_cycles):
            response = await self.client.chat.completions.create(
                model="deepseek-chat", messages=messages,
            )
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})

            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply

            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)
            if action_match:
                tool_name = action_match.group(1)
                tool_args = json.loads(input_match.group(1)) if input_match else {}
                observation = self.registry.call(tool_name, **tool_args)
                messages.append({"role": "user", "content": f"Observation: {observation}"})

        return f"{self.name} 未能完成任务"
```

### 任务 3：`src/multi_agent/supervisor.py`

```python
"""Supervisor —— 拆任务、分发给专才、汇总结果。"""

import json
from openai import AsyncOpenAI


SUPERVISOR_PROMPT = """你是一个团队主管(Supervisor)。你有以下成员可以调遣：

{team_roster}

用户给你一个任务后，你需要：
1. 分析任务需要哪些成员参与
2. 把子任务分配给对应成员
3. 收集所有成员的结果后汇总

输出格式：
Plan: 列出需要哪些成员、各自做什么
Assignments: [{{"agent": "成员名", "task": "子任务描述"}}, ...]

收到所有结果后输出：
Final Summary: [给用户的最终交付]"""


class Supervisor:
    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self.agents: dict = {}  # name → BaseAgent

    def register(self, agent) -> None:
        self.agents[agent.name] = agent

    async def run(self, user_input: str) -> str:
        team_desc = "\n".join(f"- {a.name}: {a.role}" for a in self.agents.values())
        prompt = SUPERVISOR_PROMPT.replace("{team_roster}", team_desc)

        # 1. 制定分工计划
        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"任务：{user_input}\n请制定计划并分配任务。"},
            ],
        )
        plan = response.choices[0].message.content
        print(f"=== Supervisor 计划 ===\n{plan}\n")

        # 2. 解析任务分配
        results = {}
        for name, agent in self.agents.items():
            if name in plan:
                task = self._extract_task(plan, name)
                if task:
                    print(f"--- 调度 {name} ---\n任务: {task}")
                    result = await agent.execute(task)
                    results[name] = result
                    print(f"结果: {result[:200]}\n")

        # 如果没解析出任务，让所有 agent 各尽其力
        if not results:
            for name, agent in self.agents.items():
                result = await agent.execute(user_input)
                results[name] = result

        # 3. 汇总
        context = "\n".join(f"[{name}]: {r}" for name, r in results.items())
        summary_response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是团队主管，请汇总以下成员的工作成果，给用户一个完整且有条理的 Final Answer。"},
                {"role": "user", "content": f"原始任务：{user_input}\n成员成果：\n{context}"},
            ],
        )
        return summary_response.choices[0].message.content

    def _extract_task(self, plan: str, name: str) -> str | None:
        """从计划文本中提取指定 agent 的任务。"""
        for line in plan.split("\n"):
            if name in line:
                return line.strip()
        return None
```

### 任务 4：`examples/test_team.py`

```python
"""验证 Multi-Agent 协作。"""
import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-system" / "src"))

from multi_agent.base import BaseAgent
from multi_agent.supervisor import Supervisor
from agent.tool_register import ToolRegistry
from pydantic import BaseModel, Field
from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

class CalcIn(BaseModel): expression: str = Field(description="数学表达式")
class SearchIn(BaseModel): query: str = Field(description="搜索关键词")

def calc(expression):
    expression = expression.replace("^", "**")
    try: return str(eval(expression, {"__builtins__": {}}))
    except: return "计算错误"

async def main():
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    embedder = Embedder()
    rag = RAGPipeline(llm_client=client, llm_model="deepseek-chat", embedder=embedder)
    rag.load_documents(str(Path(__file__).parent.parent.parent / "rag-system" / "data"))

    def search_rag(query):
        r = rag.store.query(query, top_k=2)
        return "\n".join([f"[{d.metadata.get('source','?')}] {d.content[:100]}" for d in r]) if r else "none"

    # 创建三个专才 Agent
    researcher_reg = ToolRegistry()
    researcher_reg.register("search_rag", "搜索知识库", search_rag, SearchIn)
    researcher = BaseAgent("Researcher", "信息检索专家，负责搜索和整理信息", client, researcher_reg)

    coder_reg = ToolRegistry()
    coder_reg.register("calculator", "数学计算", calc, CalcIn)
    coder = BaseAgent("Coder", "编程和数学专家，负责写代码和计算", client, coder_reg)

    reviewer = BaseAgent("Reviewer", "质量审查专家，负责检查结果的正确性", client, ToolRegistry())

    supervisor = Supervisor(client)
    supervisor.register(researcher)
    supervisor.register(coder)
    supervisor.register(reviewer)

    q = "搜索一下什么是RAG，然后帮我写一个判断质数的Python函数，最后计算2^10"
    print(f"Q: {q}\n")
    answer = await supervisor.run(q)
    print(f"\n{'='*60}")
    print(f"Final Answer:\n{answer}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 三、验收标准

- Supervisor 制定分工计划
- Researcher 搜到 RAG 相关资料
- Coder 写出质数判断函数 + 计算 2^10
- 最终汇总成一个完整回答

---

## 四、架构对比

| | ReAct Agent | Plan Agent | Multi-Agent |
|------|-----------|-----------|------------|
| 单个任务 | ✅ | ✅ 拆步 | ❌ 过度 |
| 多步推理 | ✅ 循环 | ✅ 计划 | ✅ 分工 |
| 需要不同专长 | ❌ 一个脑子 | ❌ 一种思路 | ✅ 多个专才 |
| 并行执行 | ❌ | ❌ | ✅ |
