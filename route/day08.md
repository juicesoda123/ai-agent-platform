# Day 08 — Chat API 深入：Messages 结构精讲

> Phase 2：LLM API 编程  |  预计用时：45 分钟  |  2026-05-05

---

## 今日目标

1. 理解 Chat API 的 messages 结构（system/user/assistant/tool 四种角色）
2. 掌握多轮对话的实现——把历史消息回传给模型
3. 学会 System Prompt 设计——给模型设定行为边界
4. 产出：一个带记忆的多轮对话 CLI

---

## 一、概念对齐：messages 是 LLM 的"眼睛"

LLM 是**无状态**的——每次调用之间什么都不记得。你要它记住上下文？把历史对话全塞回去。

```python
messages = [
    {"role": "system",    "content": "你是客服助手。"},        # 设定角色
    {"role": "user",      "content": "我的订单在哪？"},         # 用户第一句话
    {"role": "assistant", "content": "请提供订单号。"},          # 模型回复
    {"role": "user",      "content": "订单号 12345。"},         # 用户第二句话
    # ← 模型会基于上面全部内容来生成下一个回复
]
```

**四种角色**：

| role | 谁说的 | 用途 |
|------|--------|------|
| `system` | 你（开发者） | 设定 AI 的行为、边界、语气。放在第一条 |
| `user` | 终端用户 | 用户的输入 |
| `assistant` | LLM | 模型的回复。多轮对话时回传 |
| `tool` | 工具函数 | Function Calling 返回的结果。Phase 4 才用到 |

---

## 二、动手实战：多轮对话 CLI（30 分钟）

### 任务：新建 Phase 2 项目骨架

在 `AI-Agent/` 下建新项目 `llm-client/`：

```
llm-client/
├── .env                    ← 复制 ai-foundation/.env
├── .gitignore
├── src/
│   └── llm_client/
│       ├── __init__.py
│       └── chat.py         ← 今天写的：多轮对话
└── examples/
    └── cli_chat.py         ← 命令行对话机器人
```

### 文件 1：`src/llm_client/chat.py`

```python
"""多轮对话管理 —— ChatSession。

教学点：
  1. messages 列表管理——把历史消息全记住
  2. System Prompt——给模型设定角色
  3. Token 预算意识——消息太多了要裁剪（今天先记，D3 做裁剪）
"""

from dataclasses import dataclass, field
from openai import AsyncOpenAI


@dataclass
class ChatSession:
    """一次多轮对话会话。"""

    client: AsyncOpenAI
    model: str
    system_prompt: str
    history: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """初始化后自动把 system prompt 加进历史。"""
        self.history.append({"role": "system", "content": self.system_prompt})

    async def send(self, user_input: str) -> str:
        """发送一条用户消息，返回模型回复。自动维护对话历史。"""
        # 1. 把用户输入加进历史
        self.history.append({"role": "user", "content": user_input})

        # 2. 调 API
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
        )

        # 3. 提取回复
        reply = response.choices[0].message.content

        # 4. 把模型回复也加进历史
        self.history.append({"role": "assistant", "content": reply})

        return reply

    @property
    def message_count(self) -> int:
        """当前历史消息数（不含 system prompt）。"""
        return len(self.history) - 1
```

### 文件 2：`examples/cli_chat.py`

```python
"""命令行多轮对话机器人——测试 ChatSession。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_client.chat import ChatSession
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是 Python 学习助手，用中文回答，每次回答不超过两句话。",
    )

    print("多轮对话 CLI（输入 /quit 退出，/history 看历史）\n")

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            print("再见！")
            break
        if user_input == "/history":
            for i, msg in enumerate(session.history):
                print(f"  [{msg['role']}] {msg['content'][:80]}...")
            continue

        reply = await session.send(user_input)
        print(f"AI: {reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

### 创建项目骨架

在 `llm-client/` 目录下创建：

1. `.env` — 从 `ai-foundation/.env` 复制
2. `.gitignore` — 同 `ai-foundation/.gitignore`
3. `src/llm_client/__init__.py` — 空文件或一行 docstring
4. 上面两个 Python 文件

---

## 三、验收标准

运行 CLI，测试多轮对话：

```bash
cd llm-client && python examples/cli_chat.py
```

测试三轮对话，验证模型记住了上下文：

```
你: 我叫小明，我在学 Python。
AI: 你好小明！Python 是很好的入门语言...

你: 我叫什么名字？
AI: 你叫小明。   ← 记住上下文了！

你: /quit
```

---

## 四、概念速查

### LLM 的"记忆"是怎么实现的

```
第 1 轮：messages = [system, user("我叫小明")]
         模型回复: "你好小明"
         下一轮 messages = [system, user("我叫小明"), assistant("你好小明")]

第 2 轮：messages = [system, user("我叫小明"), assistant("你好小明"), user("我叫什么")]
         模型回复: "你叫小明"  ← 因为它看到了历史里的 "我叫小明"
```

**本质**：不是模型有记忆，是**你把所有历史塞回去了**。代价是每轮 token 消耗越来越大——这就是为什么 Phase 3 要做 Token 管理。
