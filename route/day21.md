# Day 21 — Tool 注册机制：自动化工具管理

> Phase 4：单 Agent 开发  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 用 Pydantic 自动生成工具的 JSON Schema
2. 实现 `ToolRegistry`——注册、查找、Schema 生成一站式
3. 淘汰手写 `SYSTEM_PROMPT` 里的工具列表——改成动态生成
4. 产出：`ToolRegistry` + 动态 System Prompt

---

## 一、概念对齐：为什么要自动化工具管理

你现在的问题——每加一个工具要改三处：

```python
# 1. 写函数
def new_tool(xxx): ...

# 2. 手写注册
agent.register_tool("new_tool", new_tool)

# 3. 手改 SYSTEM_PROMPT
SYSTEM_PROMPT = """...可用工具：
- calculator: ...
- search_rag: ...
- new_tool: ..."""            # ← 每次都手动加
```

改成自动化后只用——**定义函数 + 一行注册**，System Prompt 自动生成。

---

## 二、动手实战（30 分钟）

### 任务 1：创建 `tool_registry.py`

在 `src/agent/tool_registry.py`：

```python
"""Tool Registry —— 自动化工具管理。

教学点：
  1. Pydantic → JSON Schema：自动生成工具参数定义
  2. Tool 元数据：name / description / func / schema 打包在一起
  3. 动态 System Prompt：工具变了 Prompt 自动更新
"""

from typing import Callable
from pydantic import BaseModel, Field, create_model


class ToolInfo:
    """单个工具的完整信息。"""

    def __init__(self, name: str, description: str, func: Callable, input_model: type[BaseModel]):
        self.name = name
        self.description = description
        self.func = func
        self.input_model = input_model

    def to_dict(self) -> dict:
        """生成给 LLM 看的工具描述。"""
        schema = self.input_model.model_json_schema()
        params = schema.get("properties", {})
        param_desc = ", ".join(
            f"{k}: {v.get('type', '?')}" for k, v in params.items()
        )
        return {
            "name": self.name,
            "description": self.description,
            "parameters": param_desc,
        }


class ToolRegistry:
    """工具注册中心——加工具、查工具、生成 Prompt。"""

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}

    def register(
        self,
        name: str,
        description: str,
        func: Callable,
        input_model: type[BaseModel],
    ) -> None:
        """注册一个工具。"""
        self._tools[name] = ToolInfo(name, description, func, input_model)

    def get(self, name: str) -> ToolInfo | None:
        return self._tools.get(name)

    def call(self, name: str, **kwargs) -> str:
        """按名称调用工具。"""
        tool = self._tools.get(name)
        if not tool:
            return f"工具 '{name}' 不存在。可用：{list(self._tools.keys())}"
        try:
            params = tool.input_model(**kwargs)  # Pydantic 自动校验
            return str(tool.func(**params.model_dump()))
        except Exception as e:
            return f"工具 '{name}' 执行错误: {e}"

    def list_tools(self) -> list[dict]:
        """返回工具列表（给 LLM 看）。"""
        return [t.to_dict() for t in self._tools.values()]

    def build_system_prompt(self, base_prompt: str) -> str:
        """动态生成 System Prompt，工具列表自动更新。"""
        tool_list = "\n".join(
            f"- {t.name}: {t.description}。参数：{t.to_dict()['parameters']}"
            for t in self._tools.values()
        )
        return f"""{base_prompt}

可用工具：
{tool_list}

规则：
1. 每次只能调用一个工具
2. 严格使用 JSON 格式：Action Input: {{"参数名": "值"}}
3. 工具结果以 Observation 返回，拿到足够信息后给出 Final Answer
4. 不要编造信息"""
```

### 任务 2：改造 `react_agent.py`——用 ToolRegistry

```python
"""ReAct Agent —— 使用 ToolRegistry 管理工具。"""
import json, re
from openai import AsyncOpenAI
from agent.tool_registry import ToolRegistry

BASE_SYSTEM_PROMPT = """你是一个自主 Agent，可以调用工具回答问题。严格按以下格式响应：

当需要调用工具时：
Thought: [当前思考]
Action: [工具名称]
Action Input: [JSON 参数]

当有足够信息时：
Thought: [最终思考]
Final Answer: [中文回答]"""


class ReActAgent:
    def __init__(self, client: AsyncOpenAI, model: str = "deepseek-chat"):
        self.client = client
        self.model = model
        self.registry = ToolRegistry()
        self.history: list[dict] = []

    async def run(self, user_input: str, max_cycles: int = 5) -> str:
        if not self.history:
            system_prompt = self.registry.build_system_prompt(BASE_SYSTEM_PROMPT)
            self.history.append({"role": "system", "content": system_prompt})

        self.history.append({"role": "user", "content": user_input})

        for _ in range(max_cycles):
            response = await self.client.chat.completions.create(
                model=self.model, messages=self.history,
            )
            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            print(f"--- Step {_ + 1} ---\n{reply}\n")

            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply

            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if not action_match:
                self.history.append({"role": "user", "content": "请按格式输出"})
                continue

            tool_name = action_match.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}
            observation = self.registry.call(tool_name, **tool_args)

            print(f"Observation: {observation[:200]}")
            self.history.append({"role": "user", "content": f"Observation: {observation}"})

        return "达到最大步数。"
```

### 任务 3：更新测试

在 `examples/test_agent.py` 用新 API：

```python
from agent.react_agent import ReActAgent
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，如 3**5+100")

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")

# ... RAG 初始化同 D20 ...

agent = ReActAgent(client)
agent.registry.register("calculator", "执行数学计算", calculator, CalculatorInput)
agent.registry.register("search_rag", "搜索知识库文档", search_rag, SearchInput)
```

---

## 三、验收标准

运行测试——Agent 行为不变：能算数、能搜 RAG、能闲聊。但 System Prompt 由 `build_system_prompt()` 自动生成，加新工具只改一行注册代码。

---

## 四、概念速查：你刚实现了什么

```
之前：加工具 → 改 3 处代码（函数 + register + 手写 Prompt）
现在：加工具 → 改 2 行（Pydantic Model + registry.register()）
```

Pydantic 自动生成参数 Schema → 嵌入 System Prompt → LLM 知道每个工具需要什么参数。你在 Phase 1 D3 学的 Pydantic 在 Agent 里终于物归原主了。
