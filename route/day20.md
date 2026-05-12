# Day 20 — Agent 集成 RAG：真知识库搜索

> Phase 4：单 Agent 开发  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 把 Phase 3 的 `RAGPipeline` 接进 Agent 的 `search_rag` 工具
2. 让 Agent 能真正搜索你的知识库文档
3. 让 Agent 多轮对话——记住上下文
4. 产出：一个能聊天 + 能搜知识库 + 能算数 的智能 Agent

---

## 一、动手实战（30 分钟）

### 任务 1：升级 `test_agent.py`——接真 RAG

改 `single-agent/examples/test_agent.py`，把假 `search_rag` 换成 Phase 3 的真管道：

```python
"""Agent 集成 RAG —— 真实的工具调用。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# 把 rag-system 也加到搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-system" / "src"))

from agent.react_agent import ReActAgent
from openai import AsyncOpenAI
from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from dotenv import load_dotenv
import os

load_dotenv()

DATA_DIR = str(Path(__file__).parent.parent.parent / "rag-system" / "data")


def calculator(expression: str) -> str:
    expression = expression.replace("^", "**")
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return f"表达式包含不安全字符。允许：数字、+-*/().%。收到：{expression}"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"


async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    # 初始化真 RAG
    embedder = Embedder()
    rag = RAGPipeline(llm_client=client, llm_model="deepseek-chat", embedder=embedder)
    rag.load_documents(DATA_DIR)

    # 用 RAG 的 ask 方法作为搜索工具——但这里我们只要检索，不需要 LLM 生成
    def search_rag(query: str) -> str:
        results = rag.store.query(query, top_k=3)
        if not results:
            return "未找到相关文档"
        parts = []
        for i, doc in enumerate(results):
            src = doc.metadata.get("source", "?")
            parts.append(f"[{src}] {doc.content[:200]}")
        return "\n\n".join(parts)

    agent = ReActAgent(client)
    agent.register_tool("calculator", calculator)
    agent.register_tool("search_rag", search_rag)

    print("=" * 60)
    print("AI Agent 已就绪。输入 /quit 退出。")
    print("=" * 60)

    # 多轮对话
    while True:
        user_input = input("\n你: ").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            break

        answer = await agent.run(user_input, max_cycles=5)
        print(f"\nAgent: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 任务 2：给 Agent 加上对话记忆

在 `react_agent.py` 的 `run` 方法里，把每次对话的 messages 保存下来，实现多轮记忆：

```python
class ReActAgent:
    def __init__(self, client: AsyncOpenAI, model: str = "deepseek-chat"):
        self.client = client
        self.model = model
        self.tools: dict = {}
        self.history: list[dict] = []  # 新增：对话历史

    async def run(self, user_input: str, max_cycles: int = 5) -> str:
        # 首次对话时加入 system prompt
        if not self.history:
            self.history.append({"role": "system", "content": SYSTEM_PROMPT})

        self.history.append({"role": "user", "content": user_input})

        for _ in range(max_cycles):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
            )
            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})

            print(f"\n--- Step {_ + 1} ---")
            print(reply)

            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply

            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if not action_match:
                self.history.append({
                    "role": "user",
                    "content": "请按格式输出：Thought/Action/Action Input 或 Final Answer",
                })
                continue

            tool_name = action_match.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}

            if tool_name not in self.tools:
                observation = f"工具 '{tool_name}' 不存在。可用：{list(self.tools.keys())}"
            else:
                try:
                    result = self.tools[tool_name](**tool_args)
                    observation = str(result)
                except Exception as e:
                    observation = f"工具错误: {e}"

            print(f"Observation: {observation[:200]}")
            self.history.append({"role": "user", "content": f"Observation: {observation}"})

        return "达到最大步数限制。"
```

---

## 二、验收标准

在 VS Code 终端跑：

```bash
cd single-agent && python examples/test_agent.py
```

交互测试：
1. "什么是 RAG？" → Agent 调 search_rag，返回真实文档内容
2. "RAG 的工作流程有几个步骤？" → 基于上一轮的记忆，直接回答（不用重复搜）
3. "3 的 10 次方等于多少？" → Agent 调 calculator

三项都过 D20 完成。

---

## 三、你现在的 Agent 架构

```
用户输入
   ↓
ReActAgent.run()
   ↓
┌─ Thought ──→ Action? ──→ calculator ──→ Observation ──┐
│              Action? ──→ search_rag ──→ Observation ──┤
│              Action? ──→ Final Answer                  │
└────────────────────────────────────────────────────────┘
   ↓
最终答案
```
