

# Day 10 — Token 管理：计数 / 裁剪 / 预算

> Phase 2：LLM API 编程  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解 Token 是什么、为什么 AI 项目必须管它
2. 学会用 `tiktoken` 精确计算 token 数
3. 实现 Context Window 自动裁剪——消息太多时删最老的
4. 给 ChatSession 加上 Token 预算

---

## 一、概念对齐：Token 的三重约束

| 约束 | 说明 | DeepSeek 上限 |
|------|------|-------------|
| **Context Window** | 一次请求最多塞多少 token | 128K |
| **Max Output** | 模型最多生成多少 token | 8K |
| **计费** | 按 token 数收费 | 输入 ¥1/百万 token，输出 ¥2/百万 token |

**多轮对话的问题**：每轮对话都把历史消息全塞回去，消息越来越多，总有一轮会突破 Context Window——然后 API 直接拒绝你的请求。

```
第 1 轮：500 tokens  ← 正常
第 5 轮：2500 tokens ← 还 OK
第 20 轮：10000 tokens ← 开始慢了
第 50 轮：50000 tokens ← 贵 + 慢
第 200 轮：200000 tokens ← 💥 超出 128K，API 直接报错
```

---

## 二、语法速查

```python
import tiktoken

# 加载编码器
enc = tiktoken.get_encoding("cl100k_base")  # GPT-4/DeepSeek 都用这个

# 计算 token 数
text = "Hello, world!"
tokens = enc.encode(text)
print(len(tokens))  # 4

# 裁剪到指定 token 数
def trim_messages(messages: list[dict], max_tokens: int) -> list[dict]:
    total = 0
    result = []
    for msg in reversed(messages):  # 从最新往前保留
        n = len(enc.encode(msg["content"]))
        if total + n > max_tokens:
            break
        result.insert(0, msg)
        total += n
    return result
```

---

## 三、动手实战（25 分钟）

### 任务 1：安装 tiktoken

```bash
pip install tiktoken
```

### 任务 2：给 ChatSession 加上 Token 管理

在 `chat.py` 里改造 `ChatSession`：

```python
import tiktoken  # 加在文件顶部 import


@dataclass
class ChatSession:
    client: AsyncOpenAI
    model: str
    system_prompt: str
    history: list[dict] = field(default_factory=list)
    max_history_tokens: int = 4000  # 新增：历史消息最多占多少 token

    _encoder: tiktoken.Encoding = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._encoder = tiktoken.get_encoding("cl100k_base")
        self.history.append({"role": "system", "content": self.system_prompt})

    def _count_tokens(self) -> int:
        """计算当前 history 的总 token 数。"""
        total = 0
        for msg in self.history:
            total += len(self._encoder.encode(msg["content"]))
        return total

    def _trim_history(self) -> None:
        """如果 token 超预算，从最老的消息开始删除（保留 system prompt）。"""
        while self._count_tokens() > self.max_history_tokens and len(self.history) > 1:
            removed = self.history.pop(1)  # 删除 index=1（跳过 system prompt）
            print(f"  [Token 裁剪] 删除了: {removed['role']} - {removed['content'][:30]}...")

    async def send(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        self._trim_history()  # 发请求前裁剪

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
        )

        reply = response.choices[0].message.content
        self.history.append({"role": "assistant", "content": reply})
        return reply

    # send_stream 也加上裁剪，逻辑同上
```

### 任务 3：验证脚本

在 `examples/` 下新建 `test_token_limit.py`：

```python
"""验证 Token 自动裁剪——模拟超长对话。"""
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

    # 故意设很小的 token 预算，触发裁剪
    session = ChatSession(
        client=client,
        model="deepseek-chat",
        system_prompt="你是 AI 助手。",
        max_history_tokens=200,  # 很小的预算
    )

    # 连续发多条长消息
    long_text = "Python 是一种广泛使用的高级编程语言。" * 10  # 约 100+ chars
    for i in range(5):
        reply = await session.send(f"第 {i+1} 轮: {long_text}")
        print(f"第 {i+1} 轮完成，当前消息数: {session.message_count}")
        print(f"  token 估算: {session._count_tokens()}")

    print(f"\n最终 history 消息数: {session.message_count}")
    print("Token 裁剪功能正常！")


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
cd llm-client && python examples/test_token_limit.py
```

---

## 四、验收标准

预期看到 `[Token 裁剪]` 日志输出，证明消息超预算时自动删除了旧消息。最终 history 数控制在一个较小的值（不是 5 轮 × 2 = 10 条消息越积越多）。

---

## 五、概念速查

### Token 和汉字的换算

```
英文：1 token ≈ 0.75 个单词（"Hello world" ≈ 2-3 tokens）
中文：1 token ≈ 1.5-2 个汉字（"你好" ≈ 1-2 tokens）
代码：1 token ≈ 0.5-1 个字符（缩进/括号占大量 token）

估算公式：中文 token ≈ 字符数 / 1.5
```

### 为什么用 cl100k_base

这是 OpenAI 的编码器名称，DeepSeek 也兼容这个编码。不同的模型可能用不同的编码器，但 `cl100k_base` 是目前最通用的。
