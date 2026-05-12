# Day 05 — 异常处理 + 重试机制

> Phase 1：Python 工程补强  |  预计用时：45-60 分钟  |  2026-05-05

---

## 今日目标

1. 学会 try/except 的完整用法
2. 理解 LLM API 为什么需要重试（网络抖动/限流/服务不可用）
3. 实现指数退避重试（Exponential Backoff）
4. 产出：给 DeepSeekClient 加上自动重试，3 次失败后才抛出异常

---

## 一、概念对齐：为什么 LLM 调用需要重试

LLM API 不是本地函数调用——它走网络，会炸的原因：

| 失败类型 | 原因 | 重试有用吗 |
|---------|------|-----------|
| 网络超时 | 丢包/DNS 抖动 | ✅ 重试大概率恢复 |
| 429 限流 | 请求太快被限 | ✅ 等几秒再试 |
| 5xx 服务器错误 | API 服务临时故障 | ✅ 换个时间就好了 |
| 401 未授权 | API Key 错误 | ❌ 重试没用，直接报错 |
| 400 参数错误 | 你传的参数不对 | ❌ 重试没用，修代码 |

**关键认知**：不是所有错误都要重试。4xx 是"你的问题"，5xx 是"它的问题"。

---

## 二、语法速查

```python
import asyncio

# 基础 try/except
try:
    result = await call_api()
except APITimeoutError:
    print("超时了，重试...")
except APIRateLimitError:
    print("限流了，等几秒再试...")
except Exception:
    print("其他错误")
else:
    print(f"成功！结果: {result}")  # try 里没报错才执行
finally:
    print("无论如何都执行")          # 清理资源用

# 指数退避：每次等待时间翻倍
# 第 1 次重试等 1 秒，第 2 次等 2 秒，第 3 次等 4 秒
for attempt in range(3):
    try:
        result = await call_api()
        break  # 成功就跳出
    except Exception:
        wait = 2 ** attempt  # 1, 2, 4
        print(f"第 {attempt+1} 次失败，等 {wait}s 后重试")
        await asyncio.sleep(wait)
```

---

## 三、动手实战（35 分钟）

### 任务：给 DeepSeekClient 加上重试

打开 `deepseek_impl.py`，在 `_complete` 方法里加入重试逻辑。

**要求**：
- 最多重试 3 次
- 指数退避：等 1s → 2s → 4s
- 只在网络/服务器错误时重试（`APIConnectionError`, `APIStatusError` 且状态码 >= 500）
- API Key 错误（401）或参数错误（400）直接抛，不重试

**改 `deepseek_impl.py` 的 `_complete` 方法**：

```python
import asyncio  # 新增 import，放在文件顶部
from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APIStatusError,
)

MAX_RETRIES = 3


async def _complete(self, messages: list[Message]) -> LLMResponse:
    dict_messages = [msg.to_dict() for msg in messages]
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=dict_messages,
            )
            return LLMResponse(
                content=response.choices[0].message.content,
                model=self.model,
                tokens_used=response.usage.total_tokens,
            )
        except APIConnectionError as e:
            last_error = e
            print(f"  [网络错误] 第 {attempt+1}/{MAX_RETRIES} 次失败，{e}")
        except APIStatusError as e:
            # 4xx 不重试——是你的问题
            if e.status_code < 500:
                raise
            last_error = e
            print(f"  [服务器错误 {e.status_code}] 第 {attempt+1}/{MAX_RETRIES} 次失败")

        if attempt < MAX_RETRIES - 1:  # 最后一次不 sleep
            await asyncio.sleep(2 ** attempt)  # 1, 2, 4 秒

    raise last_error  # 重试全部失败，抛出最后一个错误
```

### 验证脚本

在 `examples/` 下新建 `test_retry.py`：

```python
"""验证重试机制——构造一个错误 URL 触发网络错误。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.deepseek_impl import DeepSeekClient


async def main() -> None:
    config = LLMConfig()

    print("=== 测试 1：正常调用 ===")
    client = DeepSeekClient(
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
    )
    r = await client.chat(user_message="说一个数字。")
    print(f"成功: {r.content}\n")

    print("=== 测试 2：错误 URL（触发重试） ===")
    bad_client = DeepSeekClient(
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url="https://api.deepseek-typo-wrong.com",  # 故意写错的 URL
    )
    try:
        r = await bad_client.chat(user_message="Hello")
        print(f"成功: {r.content}")
    except Exception as e:
        print(f"\n重试全部失败后抛出: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
cd ai-foundation && python examples/test_retry.py
```

---

## 四、验收标准

预期输出类似：

```
=== 测试 1：正常调用 ===
成功: 42。

  [网络错误] 第 1/3 次失败，...
  [网络错误] 第 2/3 次失败，...
  [网络错误] 第 3/3 次失败，...

=== 测试 2：错误 URL（触发重试） ===
重试全部失败后抛出: APIConnectionError: ...
```

关键点——测试 1 正常通过，测试 2 尝试 3 次后才报错。看到 `第 1/3` `第 2/3` `第 3/3` 就说明重试生效了。

---

## 五、概念速查

### 异常处理三原则

1. **只捕获你预期会发生的异常**——不要 `except Exception` 一把梭
2. **4xx 不重试，5xx 才重试**——区分"你的错"和"它的错"
3. **重试要有上限 + 间隔**——不设上限 = 无限循环 = 生产事故
