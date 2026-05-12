# Day 22 — Plan-and-Execute：复杂任务自动拆解

> Phase 4：单 Agent 开发  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解 Plan-and-Execute 和纯 ReAct 的区别
2. 实现 PlanAgent——先列计划，再逐步执行
3. 产出：`PlanAndExecuteAgent`，能拆解多步推理任务

---

## 一、概念对齐：ReAct vs Plan-and-Execute

```
ReAct（你现在）:               Plan-and-Execute（今天做）:
用户问 → 一步一想一调工具      用户问 → 先列完整计划 → 逐步执行 → 更新计划
        每次只考虑"下一步"               看到全局再行动
```

**例子**："对比 AI 和 ML，各举 3 个应用场景，最后用计算器算一下 2^10"

ReAct 可能边查边算但结构混乱。Plan-and-Execute 会：

```
Plan:
1. search_rag("人工智能 应用场景")     → 收集 AI 应用
2. search_rag("机器学习 应用场景")     → 收集 ML 应用
3. calculator("2^10")                  → 计算结果
4. 整合 → Final Answer

执行：Step 1 → 记录结果 → Step 2 → 记录结果 → Step 3 → 记录 → Step 4
```

---

## 二、动手实战（30 分钟）

### 任务 1：创建 `plan_agent.py`

在 `src/agent/plan_agent.py`：

```python
"""Plan-and-Execute Agent —— 先列计划再执行。

与 ReActAgent 的区别：
  ReAct: 每步只想"下一步做什么"
  PlanExecute: 先看全局，列出完整计划，再逐步执行
"""

import json
import re
from openai import AsyncOpenAI


PLANNER_PROMPT = """你是一个任务规划专家。用户会给你一个问题，你需要把它拆解成可执行的步骤。

输出格式：
Plan:
1. [工具名] 具体操作描述 (参数: key=value)
2. [工具名] 具体操作描述 (参数: key=value)
...

规则：
- 每步必须对应一个可用工具
- 步骤之间可以有依赖（后面步骤可以引用前面步骤的结果）
- 如果问题简单，可以用一个步骤完成"""

EXECUTOR_PROMPT = """你正在执行一个预设计划。根据当前步骤的 Observation，判断是否继续执行下一步。

如果所有步骤完成，给出 Final Answer。
如果还需要信息，指出下一步的 Action 和 Action Input。

格式（继续执行）：
Thought: [分析]
Action: [工具名]
Action Input: [JSON]

格式（全部完成）：
Thought: [最终分析]
Final Answer: [完整回答]"""


class PlanAndExecuteAgent:
    """先规划，再执行。"""

    def __init__(self, client: AsyncOpenAI, registry):
        self.client = client
        self.registry = registry

    async def run(self, user_input: str, max_steps: int = 8) -> str:
        # ——— Phase 1: 制定计划 ———
        tools_desc = self.registry.list_tools()
        plan_prompt = PLANNER_PROMPT + f"\n\n可用工具：{json.dumps(tools_desc, ensure_ascii=False, indent=2)}"

        plan_response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": plan_prompt},
                {"role": "user", "content": f"请为以下问题制定计划：{user_input}"},
            ],
        )
        plan_text = plan_response.choices[0].message.content
        print(f"=== 计划 ===\n{plan_text}\n")

        # 解析计划步骤
        plan_steps = re.findall(r"\d+\.\s*(\w+)", plan_text)

        # ——— Phase 2: 执行计划 ———
        context = []  # 收集每步结果
        messages = [
            {"role": "system", "content": EXECUTOR_PROMPT},
            {"role": "user", "content": f"原始问题：{user_input}\n\n计划：\n{plan_text}\n\n开始执行。"},
        ]

        for step_idx in range(min(len(plan_steps), max_steps)):
            response = await self.client.chat.completions.create(
                model="deepseek-chat", messages=messages,
            )
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})
            print(f"--- Step {step_idx + 1} ---\n{reply}\n")

            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply

            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if not action_match:
                break

            tool_name = action_match.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}
            observation = self.registry.call(tool_name, **tool_args)

            context.append(f"Step {step_idx + 1} 结果: {observation}")
            print(f"Observation: {observation[:200]}\n")
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        # ——— Phase 3: 汇总 ———
        context_str = "\n".join(context)
        summary_response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "根据以下执行结果，用中文给用户一个完整回答。"},
                {"role": "user", "content": f"问题：{user_input}\n\n执行结果：\n{context_str}\n\n请给出 Final Answer。"},
            ],
        )
        return summary_response.choices[0].message.content
```

### 任务 2：测试

在 `examples/test_plan_agent.py`：

```python
"""验证 Plan-and-Execute —— 复杂多步任务。"""
import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-system" / "src"))

from agent.plan_agent import PlanAndExecuteAgent
from agent.tool_register import ToolRegistry
from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()

class CalcIn(BaseModel): expression: str = Field(description="数学表达式")
class SearchIn(BaseModel): query: str = Field(description="搜索关键词")

def calc(expression):
    expression = expression.replace("^", "**")
    if not all(c in set("0123456789+-*/().% ") for c in expression): return "bad"
    try: return str(eval(expression, {"__builtins__": {}}))
    except Exception as e: return f"err:{e}"

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

    registry = ToolRegistry()
    registry.register("calculator", "数学计算", calc, CalcIn)
    registry.register("search_rag", "搜索知识库", search_rag, SearchIn)

    agent = PlanAndExecuteAgent(client, registry)

    # 复杂任务：需要搜索 + 计算
    q = "AI有哪些应用？机器学习又是什么？顺便算一下 2 的 10 次方。"
    print(f"Q: {q}\n")
    answer = await agent.run(q)
    print(f"\n>>> Final Answer:\n{answer}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 三、验收标准

- Agent 先输出 Plan（列了步骤），再逐步执行
- 最终回答同时覆盖了 AI/ML 概念查询 + 计算任务
- 可以对比 D19 ReActAgent 的差异——PlanAgent 更有条理

---

## 四、ReAct vs Plan-and-Execute 适用场景

| | ReAct | Plan-and-Execute |
|------|------|-----------------|
| 简单问题 | ✅ 快 | ❌ 过度规划 |
| 复杂多步任务 | ❌ 可能迷路 | ✅ 有全局视图 |
| Token 消耗 | 低 | 高（多一次规划调用） |
| 用什么场景 | 对话、单步查询 | 分析报告、多源信息整合 |
