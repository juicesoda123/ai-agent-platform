"""成本控制 —— Token 计费 / 预算管理 / 模型降级。

定价数据来源：各模型官方 2025-05 定价（RMB/百万 token）

用法:
    tracker = CostTracker(daily_budget=5.0)
    tracker.record(model="deepseek-chat", input_tokens=200, output_tokens=100)
    tracker.record(model="deepseek-chat", input_tokens=500, output_tokens=300)

    print(tracker.daily_cost)    # 今日累计
    print(tracker.is_over_budget) # 是否超预算
    print(tracker.recommend_model())  # 推荐用哪个模型
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 模型定价表（RMB / 百万 token，输入/输出分开计）
# ============================================================

@dataclass
class ModelPricing:
    name: str
    input_price: float   # RMB per 1M input tokens
    output_price: float  # RMB per 1M output tokens
    tier: int = 1        # 1=便宜 2=中等 3=贵


MODEL_PRICES: dict[str, ModelPricing] = {
    "deepseek-chat":      ModelPricing("DeepSeek V3", 2.0, 8.0, tier=1),
    "deepseek-reasoner":  ModelPricing("DeepSeek R1", 4.0, 16.0, tier=2),
    "deepseek-v4-pro":    ModelPricing("DeepSeek V4 Pro", 3.0, 12.0, tier=2),
    "deepseek-v4-flash":  ModelPricing("DeepSeek V4 Flash", 1.0, 4.0, tier=1),
    "gpt-4o":             ModelPricing("GPT-4o", 17.5, 70.0, tier=3),
    "gpt-4o-mini":        ModelPricing("GPT-4o Mini", 1.0, 4.0, tier=1),
    "gpt-3.5-turbo":      ModelPricing("GPT-3.5 Turbo", 3.5, 10.5, tier=1),
    "claude-3.5-sonnet":  ModelPricing("Claude 3.5 Sonnet", 21.0, 105.0, tier=3),
    "claude-3.5-haiku":   ModelPricing("Claude 3.5 Haiku", 5.6, 28.0, tier=2),
    "qwen-turbo":         ModelPricing("Qwen Turbo", 2.0, 6.0, tier=1),
}


# 降级链：预算不够时优先切到同 tier 的便宜模型
FALLBACK_CHAIN: dict[str, str] = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4o-mini": "deepseek-chat",
    "claude-3.5-sonnet": "claude-3.5-haiku",
    "deepseek-reasoner": "deepseek-chat",
}


# ============================================================
# 使用记录
# ============================================================

@dataclass
class UsageRecord:
    timestamp: float
    model: str
    input_tokens: int
    output_tokens: int
    cost: float


# ============================================================
# CostTracker
# ============================================================

class CostTracker:
    """成本追踪器 —— 记录每次 LLM 调用的 token 消费，累积到日/月预算。"""

    def __init__(
        self,
        daily_budget: float = 10.0,
        monthly_budget: float = 200.0,
        alert_threshold: float = 0.8,  # 80% 时告警
    ):
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self.alert_threshold = alert_threshold
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()

    # ---- 记录 ----

    def record(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> float:
        """记录一次调用，返回花费（RMB）。"""
        pricing = MODEL_PRICES.get(model)
        if not pricing:
            pricing = ModelPricing(model, 5.0, 20.0)
        cost = (
            input_tokens / 1_000_000 * pricing.input_price
            + output_tokens / 1_000_000 * pricing.output_price
        )
        with self._lock:
            self._records.append(UsageRecord(
                timestamp=time.time(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            ))
        return cost

    def record_from_spans(self, spans: list) -> float:
        """从 Tracer 的 Span 列表中提取 LLM span，批量记录。"""
        total = 0.0
        for s in spans:
            if hasattr(s, 'type') and str(s.type) == 'llm' and hasattr(s, 'tokens'):
                total += self.record(
                    model=getattr(s, 'model', 'unknown'),
                    input_tokens=getattr(s, 'tokens', 0) // 2,
                    output_tokens=getattr(s, 'tokens', 0) // 2,
                )
        return total

    # ---- 统计 ----

    @property
    def daily_cost(self) -> float:
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            return sum(
                r.cost for r in self._records
                if time.strftime("%Y-%m-%d", time.localtime(r.timestamp)) == today
            )

    @property
    def monthly_cost(self) -> float:
        this_month = time.strftime("%Y-%m")
        with self._lock:
            return sum(
                r.cost for r in self._records
                if time.strftime("%Y-%m", time.localtime(r.timestamp)) == this_month
            )

    @property
    def total_cost(self) -> float:
        with self._lock:
            return sum(r.cost for r in self._records)

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(r.input_tokens + r.output_tokens for r in self._records)

    # ---- 预算 ----

    @property
    def daily_budget_remaining(self) -> float:
        return self.daily_budget - self.daily_cost

    @property
    def monthly_budget_remaining(self) -> float:
        return self.monthly_budget - self.monthly_cost

    @property
    def is_over_budget(self) -> bool:
        return self.daily_cost >= self.daily_budget

    @property
    def is_near_budget(self) -> bool:
        return self.daily_cost >= self.daily_budget * self.alert_threshold

    # ---- 模型推荐 ----

    def recommend_model(self, preferred: str = "deepseek-chat") -> str:
        """根据预算情况推荐模型。没超预算返回首选，超了返回降级模型。"""
        if not self.is_near_budget:
            return preferred
        if not self.is_over_budget:
            # 接近预算但没超，降到同 tier 便宜模型
            return FALLBACK_CHAIN.get(preferred, "deepseek-chat")
        # 已超预算，强制最便宜
        return "deepseek-chat"

    def get_model_tier(self, model: str) -> int:
        pricing = MODEL_PRICES.get(model)
        return pricing.tier if pricing else 2

    # ---- 报告 ----

    def report(self) -> str:
        """生成人类可读的成本报告。"""
        lines = [
            "=" * 50,
            "成本报告",
            "-" * 50,
            f"今日花费:  ¥{self.daily_cost:.4f}  /  预算 ¥{self.daily_budget:.2f}  ({self.daily_cost/self.daily_budget*100:.0f}%)",
            f"本月花费:  ¥{self.monthly_cost:.4f}  /  预算 ¥{self.monthly_budget:.2f}  ({self.monthly_cost/self.monthly_budget*100:.0f}%)",
            f"总计花费:  ¥{self.total_cost:.4f}",
            f"总计 Token: {self.total_tokens:,}",
            "-" * 50,
        ]

        status = "超预算!" if self.is_over_budget else ("接近预算" if self.is_near_budget else "正常")
        lines.append(f"状态: {status}")
        lines.append(f"推荐模型: {self.recommend_model()}")

        # 按模型分组
        model_costs: dict[str, float] = {}
        with self._lock:
            for r in self._records:
                name = MODEL_PRICES.get(r.model, ModelPricing(r.model, 0, 0)).name
                model_costs[name] = model_costs.get(name, 0) + r.cost
        if model_costs:
            lines.append("-" * 50)
            for name, cost in sorted(model_costs.items(), key=lambda x: -x[1]):
                lines.append(f"  {name}: ¥{cost:.4f}")
        lines.append("=" * 50)
        return "\n".join(lines)
