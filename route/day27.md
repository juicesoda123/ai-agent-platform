# Day 27 — 可观测性：LangFuse 真实链路追踪

> Phase 6：生产化部署  |  预计用时：30 分钟  |  2026-05-08

---

## 今日目标

1. 理解 Agent 可观测性的三层模型（Session > Trace > Span）
2. 接入真实 LangFuse SDK，上报到云端 Dashboard
3. Console + LangFuse 双出口，本地调试和线上监控两不误
4. 产出：`agent_platform/tracing.py` + 真实 DeepSeek+LangFuse 集成验证

---

## 一、概念对齐：可观测性三层模型

### 为什么需要可观测性

Agent 不是一个函数调用——它是 LLM + 工具 + 护栏的多轮链路。出了问题，你需要知道：
- 哪一轮 LLM 调用花了 5 秒？token 用了多少？
- 哪个工具调用失败了？传了什么参数？
- 护栏拦截了哪次输入？

没有 Trace，你只能猜。

### 三层模型

```
Session（一次对话）
  └── Trace（一次 Agent.run()）
        ├── Span: LLM call     — 耗时 / token / 模型 / 输入输出
        ├── Span: Tool call    — 工具名 / 参数 / 结果 / 耗时
        └── Span: Guard check  — 哪个护栏 / 通过否 / 原因
```

每一层 Span 都有：开始时间、结束时间、输入、输出、错误信息。LLM Span 额外记录 token 数和模型名。

### LangFuse vs 自己写

| | 自建 Console 输出 | LangFuse |
|------|-----------|---------|
| 看见 Trace | 终端打印 | Web Dashboard |
| 搜索历史 | ❌ | ✅ |
| Token 统计 | 自己算 | 自动汇总 |
| 多会话对比 | ❌ | ✅ |
| 成本计算 | ❌ | ✅ 按模型费率算 |

LangFuse 免费额度够学习用，生产环境也有 self-host 方案。

---

## 二、Tracer 架构

```
Tracer
  ├── ConsoleExporter  → print 到终端（开发用）
  ├── LangFuseExporter → 上报 LangFuse 云端（生产用）
  └── 可扩展其他 Exporter
```

**关键设计决策：多 Exporter 同时输出**。一个 Trace 完成后，遍历所有 Exporter 调用 `export()`。某个 Exporter 挂了不影响其他的。

### 用法

```python
from agent_platform.tracing import Tracer, SpanType, ConsoleExporter, LangFuseExporter

tracer = Tracer([
    ConsoleExporter(),
    LangFuseExporter(),   # 自动读取 LANGFUSE_* 环境变量
])

trace = tracer.start_trace("用户问题")

# LLM 调用
with tracer.span("deepseek-chat", SpanType.LLM) as s:
    s.tokens = response.usage.total_tokens
    s.model = "deepseek-chat"
    s.output = response.choices[0].message.content

# 工具调用
with tracer.span("calculator", SpanType.TOOL) as s:
    s.input = {"expression": "2+3"}
    s.output = calculator("2+3")

tracer.finish_trace(trace, "最终回答")
```

### 环境变量配置

```bash
# .env
LANGFUSE_SECRET_KEY=sk-lf-...   # 从 LangFuse Project Settings 获取
LANGFUSE_PUBLIC_KEY=pk-lf-...   # 同上
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com  # US 区域
```

---

## 三、验收标准

```bash
cd agent-platform && python examples/test_tracing_live.py
```

1. **终端输出**：Console Trace 完整，含耗时/token/状态
2. **LangFuse 上报**：日志显示 `[LangFuse] Trace xxx 已上报`
3. **Dashboard 可见**：打开 cloud.langfuse.com → Traces → 看到 1 条 agent-run，内嵌 3 个子 Span

```
Trace: 07639e6ceb6b
输入: 7 的 3 次方加上 50 等于多少？
总耗时: 5052ms | Spans: 3 | Tokens: 197 | Errors: 0
------------------------------------------------------------
  [LLM] deepseek-chat | 3783ms | OK | tokens=116
  [TOOL] calculator | 0ms | OK
  [LLM] deepseek-chat | 1269ms | OK | tokens=81
输出: 7³ + 50 = 393
```

---

## 四、LangFuse 注册步骤

1. 打开 [cloud.langfuse.com](https://cloud.langfuse.com) → GitHub 登录
2. Create Organization → Create Project
3. Project Settings → API Keys → Create new API keys
4. 把 `sk-lf-...` 和 `pk-lf-...` 填入 `.env`

---

## 五、Span 类型速查

| SpanType | LangFuse as_type | 记录内容 |
|----------|-----------------|---------|
| `LLM` | generation | model, tokens, input/output |
| `TOOL` | tool | tool_name, arguments, result |
| `GUARD` | guardrail | guard_name, passed/blocked, reason |
