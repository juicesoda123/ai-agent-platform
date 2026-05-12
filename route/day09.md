# Day 09 — 流式输出（Streaming）：一个字一个字蹦出来

> Phase 2：LLM API 编程  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解 SSE（Server-Sent Events）——服务器推流，不是客户端轮询
2. 掌握 `stream=True` 的用法
3. 给 ChatSession 加上流式输出
4. 理解 `async generator`（异步生成器）——yield 的异步版

---

## 一、概念对齐：流式 vs 非流式

```
非流式（你现在的代码）：
  发送请求 → 等 3 秒 → 一次性拿到完整回复

流式（今天要做的）：
  发送请求 → 0.3 秒后开始 → 一 → 个 → 字 → 一 → 个 → 字 → 往外蹦
```

**为什么需要流式**：用户体验。ChatGPT/Claude 都是一边生成一边显示，用户不用盯着空白屏幕等。3 秒在计算机世界是一辈子。

---

## 二、语法速查：stream=True

```python
# 非流式
response = await client.chat.completions.create(
    model="deepseek-chat",
    messages=[...],
)
print(response.choices[0].message.content)  # 一次性拿全部

# 流式
stream = await client.chat.completions.create(
    model="deepseek-chat",
    messages=[...],
    stream=True,                # ← 关键参数
)
async for chunk in stream:      # async for = 异步迭代
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
        # delta.content = 这次推来的一个字/词
        # 注意是 delta，不是 message
```

**关键差异**：

| | 非流式 | 流式 |
|------|--------|------|
| 返回 | `ChatCompletion` 对象 | `AsyncStream` 迭代器 |
| 内容位置 | `response.choices[0].message.content` | `chunk.choices[0].delta.content` |
| 阅读方式 | `await` 一次拿到 | `async for` 逐个 chunk |

---

## 三、动手实战（25 分钟）

### 任务：给 ChatSession 加流式方法

在 `chat.py` 的 `ChatSession` 类里加一个新方法 `send_stream()`：

```python
from collections.abc import AsyncGenerator  # 加在文件顶部 import


async def send_stream(self, user_input: str) -> AsyncGenerator[str, None]:
    """流式发送消息——每生成一个 chunk 就 yield 出去。

    调用方可以 async for chunk in session.send_stream("你好"):
        print(chunk, end="")  实时显示
    """
    self.history.append({"role": "user", "content": user_input})

    stream = await self.client.chat.completions.create(
        model=self.model,
        messages=self.history,
        stream=True,
    )

    full_reply = ""  # 攒齐完整回复，最后存入 history
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            full_reply += delta.content
            yield delta.content  # ← yield = 吐一个 chunk 给调用方

    # 流结束后把完整回复存入历史
    self.history.append({"role": "assistant", "content": full_reply})
```

### 验证：写一个流式 CLI

在 `examples/` 下新建 `cli_stream.py`：

```python
"""流式多轮对话——实时显示模型输出。"""
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
        system_prompt="你是 AI 助手，用中文回答。",
    )

    print("流式多轮对话（输入 /quit 退出）\n")

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input == "/quit":
            break

        print("AI: ", end="", flush=True)
        async for chunk in session.send_stream(user_input):
            print(chunk, end="", flush=True)  # 一个字一个字打印
        print("\n")  # 回复结束，换行


if __name__ == "__main__":
    asyncio.run(main())
```

然后在 VS Code 终端里跑：

```bash
cd llm-client && python examples/cli_stream.py
```

---

## 四、验收标准

1. 运行 `cli_stream.py`，问一个问题
2. 看模型回复是否**一个字一个字蹦出来**（不是一次性显示）
3. 问第二个问题——验证流式模式下多轮记忆也正常

---

## 五、概念速查：yield 和 async generator

```python
# 普通函数：return 一次性返回，函数结束
def normal():
    return "全部结果"

# 生成器：yield 多次返回，函数暂停但不结束
def generator():
    yield "第 1 块"
    yield "第 2 块"
    yield "第 3 块"

# 异步生成器：yield + await 可以一起用
async def async_gen():
    yield "第 1 块"
    await asyncio.sleep(1)
    yield "第 2 块"
```

`AsyncGenerator[str, None]` 类型注解含义：
- 第一个参数 `str` = yield 出去的值类型
- 第二个参数 `None` = send() 传进来的值类型（通常不用，写 None）
