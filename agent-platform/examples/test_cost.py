"""验证成本控制 —— 纯逻辑测试，不需要 API Key。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.cost import (
    CostTracker, MODEL_PRICES, FALLBACK_CHAIN, ModelPricing,
)

passed = 0
failed = 0

def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} — {detail}")


# ============================================================
# 1. 定价表完整性
# ============================================================
print("=== 1. 定价表 ===")

test("至少 5 个模型", len(MODEL_PRICES) >= 5, f"{len(MODEL_PRICES)} models")
test("DeepSeek 在表中", "deepseek-chat" in MODEL_PRICES)
test("降级链存在", len(FALLBACK_CHAIN) >= 2)


# ============================================================
# 2. 单次记录
# ============================================================
print("\n=== 2. 单次记录 ===")

tracker = CostTracker(daily_budget=10.0, monthly_budget=200.0)

# DeepSeek: input=2 RMB/M, output=8 RMB/M
# 1000 input + 500 output = 0.001M * 2 + 0.0005M * 8 = 0.002 + 0.004 = 0.006
cost = tracker.record("deepseek-chat", input_tokens=1000, output_tokens=500)
test("DeepSeek 计费", abs(cost - 0.006) < 0.001, f"{cost:.6f}")

# GPT-4o: input=17.5 RMB/M, output=70 RMB/M
# 1000000 input + 0 output = 1M * 17.5 = 17.5
cost = tracker.record("gpt-4o", input_tokens=1_000_000, output_tokens=0)
test("GPT-4o 计费", abs(cost - 17.5) < 0.1, f"{cost:.4f}")

# 未知模型用默认价格
cost = tracker.record("unknown-model", input_tokens=1000, output_tokens=1000)
test("未知模型默认计费", cost > 0, f"{cost:.6f}")


# ============================================================
# 3. 预算管理
# ============================================================
print("\n=== 3. 预算管理 ===")

t2 = CostTracker(daily_budget=0.10, monthly_budget=1.0, alert_threshold=0.8)
test("初始状态正常", not t2.is_over_budget and not t2.is_near_budget)

# DeepSeek: 10000 input + 10000 output = 0.01M*2 + 0.01M*8 = 0.02+0.08 = 0.10 刚好满
t2.record("deepseek-chat", input_tokens=10000, output_tokens=10000)
test("80% 触发告警", t2.is_near_budget, f"daily={t2.daily_cost:.4f}")
test("刚好满即超", t2.is_over_budget, f"daily={t2.daily_cost:.4f} = budget={t2.daily_budget}")

# 再加一点就超
t2.record("gpt-4o-mini", input_tokens=1000, output_tokens=1000)
test("超预算", t2.is_over_budget, f"daily={t2.daily_cost:.4f} > {t2.daily_budget}")

test("日预算剩余为负", t2.daily_budget_remaining < 0)


# ============================================================
# 4. 模型推荐/降级
# ============================================================
print("\n=== 4. 模型推荐 ===")

t3 = CostTracker(daily_budget=10.0, alert_threshold=0.8)
test("正常时期推荐首选", t3.recommend_model("gpt-4o") == "gpt-4o")

# 接近预算
t3.record("deepseek-chat", input_tokens=4_000_000, output_tokens=0)  # 约 8 块，80%
test("接近预算降级", t3.recommend_model("gpt-4o") == "gpt-4o-mini", t3.recommend_model("gpt-4o"))

test("tier 查询", t3.get_model_tier("deepseek-chat") == 1)
test("GPT-4o tier=3", t3.get_model_tier("gpt-4o") == 3)


# ============================================================
# 5. record_from_spans (对接 Tracer)
# ============================================================
print("\n=== 5. 对接 Tracer ===")

# 模拟 Span 对象
class MockSpan:
    def __init__(self, span_type, tokens=0, model=""):
        self.type = span_type
        self.tokens = tokens
        self.model = model

t4 = CostTracker(daily_budget=50.0)
spans = [
    MockSpan("llm", tokens=2000, model="deepseek-chat"),
    MockSpan("tool", tokens=0),           # 非 LLM，跳过
    MockSpan("llm", tokens=1500, model="deepseek-chat"),
    MockSpan("guard", tokens=0),           # 非 LLM，跳过
]
t4.record_from_spans(spans)
test("从 spans 提取 LLM", t4.total_tokens == 3500, f"{t4.total_tokens}")
test("只记录了 2 个 LLM span", len(t4._records) == 2, f"{len(t4._records)}")


# ============================================================
# 6. 报告
# ============================================================
print("\n=== 6. 报告 ===")

report = t4.report()
test("报告含标题", "成本报告" in report)
test("报告含花费", "¥" in report or "RMB" in report or "cost" in report.lower())
test("报告含推荐模型", "推荐模型" in report)


# ============================================================
# 7. GPT-4o vs DeepSeek 成本对比
# ============================================================
print("\n=== 7. 成本对比 ===")

# 假设一次对话 10K tokens (6K input + 4K output)
input_t = 6000
output_t = 4000

ds_cost = MODEL_PRICES["deepseek-chat"].input_price * input_t / 1e6 \
        + MODEL_PRICES["deepseek-chat"].output_price * output_t / 1e6
gpt4_cost = MODEL_PRICES["gpt-4o"].input_price * input_t / 1e6 \
          + MODEL_PRICES["gpt-4o"].output_price * output_t / 1e6

print(f"  DeepSeek=RMB{ds_cost:.4f}, GPT-4o=RMB{gpt4_cost:.4f}")
print(f"  GPT-4o 贵{gpt4_cost/ds_cost:.0f}x")
test("GPT-4o 比 DeepSeek 贵至少 5 倍", gpt4_cost / ds_cost > 5)


# ============================================================
print(f"\n{'='*40}")
print(f"RESULTS: {passed} passed, {failed} failed (total {passed + failed})")
print(f"{'ALL PASSED' if failed == 0 else 'SOME FAILED'}")
