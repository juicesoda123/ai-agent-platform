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
    print("[SERIAL] 串行模式")
    serial_time = await serial_call(client)
    print(f"-> 串行总耗时: {serial_time:.2f} 秒\n")

    print("=" * 50)
    print("[CONCURRENT] 并发模式")
    concurrent_time = await concurrent_call(client)
    print(f"-> 并发总耗时: {concurrent_time:.2f} 秒\n")

    print("=" * 50)
    speedup = serial_time / concurrent_time
    print(f"提速: {speedup:.1f}x")


if __name__ == "__main__":
    asyncio.run(main())