# Day 28 — 成本控制：Token 计费 + 预算 + 降级

> Phase 6：生产化部署  |  预计用时：30 分钟  |  2026-05-08

---

## 今日目标

1. 理解 LLM 成本模型——按模型/输入/输出分别计价
2. 掌握 CostTracker 的计费、预算、告警、降级四段链路
3. 对接 Tracer，从 Span 自动提取 token 数据算钱
4. 产出：`agent_platform/cost.py`，21 测试全过

---

## 一、概念对齐：为什么要管成本

一次 Agent 调用 = 多轮 LLM 对话。每轮都有 token 消耗。不加成本管控：

- 开发阶段可能一次测试花几十块
- 生产环境流量上来，一天花几百上千
- 不知道哪个模型在烧钱，切不了便宜方案

### 真实定价对比（2025-05，RMB/百万 token）

| 模型 | 输入价格 | 输出价格 | 一次 10K token 对话 |
|------|---------|---------|-------------------|
| DeepSeek V3 | ¥2 | ¥8 | ¥0.044 |
| GPT-4o Mini | ¥1 | ¥4 | ¥0.022 |
| GPT-4o | ¥17.5 | ¥70 | ¥0.385 |
| Claude 3.5 Sonnet | ¥21 | ¥105 | ¥0.546 |

GPT-4o 比 DeepSeek 贵 9 倍——但推理能力也更强。成本控制的本质是：**该用贵的用贵的，该省钱时自动降级。**

---

## 二、CostTracker 架构

```
CostTracker
  ├── record(model, input_tokens, output_tokens) → 单次花费
  ├── record_from_spans(tracer.spans)            → 对接 Tracer 自动读 token
  ├── daily_cost / monthly_cost                  → 累计统计
  ├── is_over_budget / is_near_budget            → 预算状态
  ├── recommend_model(preferred)                  → 根据预算推荐模型
  └── report()                                    → 人类可读成本报告
```

### 用法

```python
from agent_platform.cost import CostTracker

tracker = CostTracker(daily_budget=10.0, monthly_budget=200.0)

# 方式一：手动记录
tracker.record("deepseek-chat", input_tokens=500, output_tokens=200)

# 方式二：从 Tracer Span 自动提取
tracker.record_from_spans(trace.spans)

# 查状态
print(tracker.daily_cost)         # ¥0.044
print(tracker.is_over_budget)     # False
print(tracker.recommend_model())  # deepseek-chat

# 成本报告
print(tracker.report())
```

### 降级策略

```
预算正常 → 用首选模型
预算 80% → 降级到同 tier 便宜模型 (GPT-4o → GPT-4o Mini)
预算 100% → 强制最便宜 (DeepSeek)
```

降级链可配置：

```python
FALLBACK_CHAIN = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4o-mini": "deepseek-chat",
    "claude-3.5-sonnet": "claude-3.5-haiku",
    "deepseek-reasoner": "deepseek-chat",
}
```

---

## 三、与 Tracer 集成

Tracer 的 Span 里已经有 token 数据。CostTracker 一个方法调用即可对接：

```python
tracer.finish_trace(trace, final_output)

# 从 Trace 的 spans 里提取所有 LLM span 的 token
cost = cost_tracker.record_from_spans(trace.spans)
```

---

## 四、验收标准

```bash
python agent-platform/examples/test_cost.py
```

```
RESULTS: 21 passed, 0 failed
ALL PASSED
```

| 测试组 | 覆盖 |
|--------|------|
| 定价表 | 模型数量 / DeepSeek/降级链存在 |
| 单次计费 | DeepSeek / GPT-4o / 未知模型默认价 |
| 预算管理 | 正常/告警/超预算/剩余 |
| 模型推荐 | 正常/降级/tier查询 |
| Tracer 对接 | 从 spans 提取 LLM token |
| 报告 | 标题/花费/推荐模型 |
| 成本对比 | GPT-4o 比 DeepSeek 贵 9x |
