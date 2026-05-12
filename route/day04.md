# Day 04 — 异步编程：async/await/asyncio

> Phase 1：Python 工程补强  |  预计用时：45-60 分钟  |  2026-05-05

---

## 今日目标

1. 理解同步 vs 异步的本质区别——不是"快"，是"不傻等"
2. 掌握 async/await 语法
3. 学会 asyncio.gather() 并发调用
4. 产出：并发 LLM 调用——同时问 3 个问题，哪个先回来先用哪个

---

## 一、概念对齐：为什么要异步

**同步的问题**：调一次 LLM API 等 2 秒，调 3 次串行就是 6 秒。这 6 秒里你的 CPU 在**干等**——什么都不做，就等网络回包。

```python
# 同步（阻塞）：总耗时 = 2 + 2 + 2 = 6 秒
r1 = call_llm("问题1")   # 等 2 秒
r2 = call_llm("问题2")   # 等 2 秒
r3 = call_llm("问题3")   # 等 2 秒
```

**异步**：发完请求 1 不等回包就发请求 2，再发请求 3。三个请求同时在网络上飞，哪个先回来处理哪个。

```python
# 异步（非阻塞）：总耗时 ≈ 2 秒（三个请求同时发出）
r1, r2, r3 = await asyncio.gather(
    call_llm("问题1"),
    call_llm("问题2"),
    call_llm("问题3"),
)
```

**在 AI Agent 里**：一个 Agent 同时调搜索工具 + 调计算器 + 调数据库，三个工具各等 1 秒，串行 3 秒，异步 1 秒。面对用户，3 秒和 1 秒的体感天差地别。

---

## 二、语法速查

```python
import asyncio

# async def = 定义一个异步函数（协程）
async def fetch_data(url: str) -> str:
    print(f"开始请求 {url}")
    await asyncio.sleep(2)   # 模拟网络等待（实际是 await http 请求）
    print(f"{url} 完成")
    return f"{url} 的数据"

# asyncio.run() = 运行顶层异步函数
async def main() -> None:
    # 方式 1：串行执行（每个等完再下一个）
    result1 = await fetch_data("A")
    result2 = await fetch_data("B")

    # 方式 2：并发执行（同时发出）
    results = await asyncio.gather(
        fetch_data("A"),
        fetch_data("B"),
        fetch_data("C"),
    )

asyncio.run(main())
```

关键规则：
- `async def` → 定义一个协程函数，调用它不会执行，返回一个 coroutine 对象
- `await` → 等待一个协程执行完，把 CPU 让给其他协程
- `asyncio.gather()` → 并发跑多个协程，全部完成后一起返回
- 只能在 `async def` 函数里用 `await`

---

## 三、阅读代码（5 分钟）

重读 `deepseek_impl.py` 第 28 行——`async def _complete(self, messages)`，注意你已经在写异步代码了。`AsyncOpenAI` 里的 `Async` 就是异步版本，所有网络请求都是 `await` 的。

---

## 四、动手实战（30 分钟）

### 任务：并发 LLM 调用

在 `examples/` 下新建 `test_async_concurrent.py`——同时向 DeepSeek 发 3 个不同的问题，对比串行 vs 并发的耗时。

```python
"""验证异步并发——对比串行 vs 并发的耗时差异。"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.deepseek_impl import DeepSeekClient


QUESTIONS = [
    "用一句话解释 Python 的 GIL。",
    "用一句话解释什么是协程。",
    "用一句话解释 asyncio 事件循环。",
]


async def serial_call(client: DeepSeekClient) -> float:
    """串行：一个接一个调。"""
    start = time.perf_counter()
    for q in QUESTIONS:
        r = await client.chat(user_message=q)
        print(f"  串行完成: {q[:20]}... → {r.tokens_used} tokens")
    elapsed = time.perf_counter() - start
    return elapsed


async def concurrent_call(client: DeepSeekClient) -> float:
    """并发：三个请求同时发出。"""
    start = time.perf_counter()

    async def ask(q: str):
        return await client.chat(user_message=q)

    results = await asyncio.gather(
        ask(QUESTIONS[0]),
        ask(QUESTIONS[1]),
        ask(QUESTIONS[2]),
    )
    elapsed = time.perf_counter() - start
    for q, r in zip(QUESTIONS, results):
        print(f"  并发完成: {q[:20]}... → {r.tokens_used} tokens")
    return elapsed


async def main() -> None:
    config = LLMConfig()
    client = DeepSeekClient(
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
    )

    print("=" * 50)
    print("🔵 串行模式")
    serial_time = await serial_call(client)
    print(f"→ 串行总耗时: {serial_time:.2f} 秒\n")

    print("=" * 50)
    print("🟢 并发模式")
    concurrent_time = await concurrent_call(client)
    print(f"→ 并发总耗时: {concurrent_time:.2f} 秒\n")

    print("=" * 50)
    speedup = serial_time / concurrent_time
    print(f"提速: {speedup:.1f}x")


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
cd ai-foundation && python examples/test_async_concurrent.py
```

---

## 五、验收标准

预期输出类似：

```
串行总耗时: 5.23 秒
并发总耗时: 2.01 秒
提速: 2.6x
```

并发明显快于串行就过了。如果两者差不多（差距 < 20%），说明 DeepSeek API 有并发限流，不影响——你理解机制就行。

---

## 六、一张图记住 async/await

```
         async def = 我是一段可以暂停的代码
         await     = 我先停一下，你先跑，跑完叫我
asyncio.gather()   = 你们几个一起跑，我全等
   asyncio.run()   = 整个异步世界的入口
```

---

## 七、常见坑（提前防）

| 坑 | 现象 | 原因与修复 |
|----|------|-----------|
| 在同步函数里用 await | `SyntaxError` | `await` 只能在 `async def` 函数里用 |
| 忘写 await | 返回 coroutine 对象，不执行 | 调异步函数前面必须加 `await` |
| 在 Jupyter 里跑 | `RuntimeError: event loop is already running` | Jupyter 自带事件循环，直接用 `await` 就行，不需要 `asyncio.run()` |
