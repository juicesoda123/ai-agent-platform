# Day 30 — 异步并发：串行 vs 并发 vs 限流

> Phase 6：生产化部署  |  预计用时：25 分钟  |  2026-05-09

---

## 今日目标

1. 理解 `asyncio.gather` 并发模型 —— 5 个请求一起发 vs 一个一个等
2. 掌握 `asyncio.Semaphore` 限流 —— 控制并发数，防 API 限流
3. 量化提速效果 —— 串行 16.2s → 并发 8.9s

---

## 一、概念对齐：三种执行模式

```
串行:     Q1→等→结果  Q2→等→结果  Q3→等→结果    总时间 = t1+t2+t3
并发:     Q1↘
          Q2 → 全部发出 → 谁先回先处理     总时间 ≈ max(t1,t2,t3)
          Q3↗
限流并发:  Q1,Q2,Q3 同时发 → 最多 N 个同时在途   总时间 ≈ 串行/N
```

### 核心代码

```python
# 串行
for q in questions:
    await server.run(q)

# 并发 — asyncio.gather
tasks = [server.run(q) for q in questions]
results = await asyncio.gather(*tasks)

# 限流并发 — Semaphore
sem = asyncio.Semaphore(3)
async def limited(q):
    async with sem:
        return await server.run(q)
results = await asyncio.gather(*[limited(q) for q in questions])
```

## 二、Benchmark 结果

5 个数学问题，DeepSeek API：

| 模式 | 耗时 | vs 串行 |
|------|------|---------|
| 串行 | 16.2s | 基准 |
| 并发 | 8.9s | **1.8x 快** |
| 限流(max=3) | 7.4s | **2.2x 快** |
| 理论最优 | 3.2s | 单次耗时 × 完全并行 |

### 为什么限流比无限并发更稳

API 提供商通常有速率限制（RPM/TPM）。同时发太多请求可能触发限流，反而变慢。`Semaphore(3)` 保证最多 3 个请求同时在途，其他排队——既不堵、也不超。

### 什么时候用哪种

| 场景 | 推荐 | 原因 |
|------|------|------|
| 调试验证 | 串行 | 日志不混，容易排查 |
| 生产低负载 | 并发 | 吞吐最大化 |
| 生产高负载 | 限流并发 | 防 API 限流 + 保护下游 |

## 三、验收标准

```bash
PYTHONPATH="src;../single-agent/src" python examples/benchmark_concurrent.py
```

预期输出：
```
串行:        16.2s  (基准)
并发:        8.9s   (提速 1.8x)
限流(max=3): 7.4s
```

提速倍率取决于 API 延迟分布，1.5x-3x 均为正常。

---

## 四、你现在的知识地图

```
agent-platform/
├── guardrails.py    ← 安全护栏（正则 + 白名单）
├── pii.py           ← 隐私脱敏（10 种 PII 类型）
├── tracing.py       ← 可观测（Console + LangFuse）
├── cost.py          ← 成本控制（计费 + 预算 + 降级）
├── server.py        ← HTTP 服务（FastAPI 5 端点）
└── (concurrency)    ← 异步并发（asyncio.gather + Semaphore）
```

整个平台的核心链路已闭环：请求进来 → 护栏 → Agent 推理 → 工具调用 → 护栏 → PII 脱敏 → 返回，全过程带 Trace、算成本、支持并发。
