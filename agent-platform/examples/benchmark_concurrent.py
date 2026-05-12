"""异步并发 Benchmark —— 串行 vs 并发，量化提速效果。

运行:
    cd agent-platform
    PYTHONPATH="src;../single-agent/src" python examples/benchmark_concurrent.py
"""
import asyncio
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.server import AgentServer

QUESTIONS = [
    "1+1等于多少",
    "15乘以37等于多少",
    "256除以8等于多少",
    "99加101等于多少",
    "2的10次方等于多少",
]


async def run_sequential(server: AgentServer, questions: list[str]) -> tuple[list[str], float]:
    """串行：一个接一个。"""
    t0 = time.time()
    results = []
    for q in questions:
        r = await server.run(q, max_cycles=3)
        results.append(r.answer)
    return results, time.time() - t0


async def run_concurrent(server: AgentServer, questions: list[str]) -> tuple[list[str], float]:
    """并发：全部一起发出。"""
    t0 = time.time()
    tasks = [server.run(q, max_cycles=3) for q in questions]
    responses = await asyncio.gather(*tasks)
    results = [r.answer for r in responses]
    return results, time.time() - t0


async def run_concurrent_limited(
    server: AgentServer, questions: list[str], max_concurrent: int = 3
) -> tuple[list[str], float]:
    """限流并发：Semaphore 控制同时最多 N 个请求。"""
    sem = asyncio.Semaphore(max_concurrent)

    async def limited_run(q):
        async with sem:
            return await server.run(q, max_cycles=3)

    t0 = time.time()
    tasks = [limited_run(q) for q in questions]
    responses = await asyncio.gather(*tasks)
    results = [r.answer for r in responses]
    return results, time.time() - t0


async def main():
    print("=" * 60)
    print("异步并发 Benchmark: 5 个问题")
    print("=" * 60)

    server = AgentServer()

    # ---- 串行 ----
    print("\n[1/3] 串行执行...")
    answers_seq, t_seq = await run_sequential(server, QUESTIONS)
    for q, a in zip(QUESTIONS, answers_seq):
        print(f"  Q: {q:20s} → {a[:40]}")
    print(f"  串行总耗时: {t_seq:.1f}s")

    # ---- 并发 ----
    print("\n[2/3] 并发执行...")
    answers_conc, t_conc = await run_concurrent(server, QUESTIONS)
    for q, a in zip(QUESTIONS, answers_conc):
        print(f"  Q: {q:20s} → {a[:40]}")
    print(f"  并发总耗时: {t_conc:.1f}s")

    # ---- 限流并发 ----
    print("\n[3/3] 限流并发 (max=3)...")
    answers_lim, t_lim = await run_concurrent_limited(server, QUESTIONS, max_concurrent=3)
    print(f"  限流总耗时: {t_lim:.1f}s")

    # ---- 总结 ----
    speedup = t_seq / t_conc if t_conc > 0 else float("inf")
    print("\n" + "=" * 60)
    print("结果对比")
    print("-" * 60)
    print(f"  串行:        {t_seq:.1f}s  (基准)")
    print(f"  并发:        {t_conc:.1f}s  (提速 {speedup:.1f}x)")
    print(f"  限流(max=3): {t_lim:.1f}s")
    print(f"  理论最优:    {t_seq/len(QUESTIONS):.1f}s  (单次耗时 × 完全并行)")
    print("=" * 60)

    if speedup >= 1.3:
        print(f"\n并发提速 {speedup:.1f}x —— 生产环境建议用限流并发（防 API 限流）")
    else:
        print("\nAPI 响应时间相近，并发排队优势取决于下游耗时分布")


if __name__ == "__main__":
    asyncio.run(main())
