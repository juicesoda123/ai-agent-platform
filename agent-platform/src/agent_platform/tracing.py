"""Agent 可观测性 —— Trace / Span 记录，Console + LangFuse 双出口。

三层模型：
  Session > Trace > Span

Span 类型：llm / tool / guard

用法:
    tracer = Tracer([ConsoleExporter(), LangFuseExporter()])
    trace = tracer.start_trace("用户问题")
    with tracer.span("deepseek-chat", SpanType.LLM) as s:
        s.tokens = 150
        s.output = reply
    tracer.finish_trace(trace, "最终回答")
"""

import time
import os
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class SpanType(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    GUARD = "guard"


@dataclass
class Span:
    """一次原子操作记录。"""
    type: SpanType
    name: str
    start_time: float
    end_time: float = 0.0
    input: Any = None
    output: Any = None
    tokens: int = 0
    model: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2),
            "input": str(self.input)[:200] if self.input else "",
            "output": str(self.output)[:200] if self.output else "",
            "tokens": self.tokens,
            "model": self.model,
            "error": self.error,
        }


@dataclass
class Trace:
    """一次 Agent.run() 的完整记录。"""
    trace_id: str
    user_input: str
    start_time: float
    end_time: float = 0.0
    spans: list[Span] = field(default_factory=list)
    final_output: str = ""

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.spans if s.type == SpanType.LLM)

    @property
    def span_count(self) -> int:
        return len(self.spans)

    @property
    def error_count(self) -> int:
        return sum(1 for s in self.spans if s.error)


# ============================================================
# Exporters
# ============================================================

class Exporter:
    """导出器基类。"""
    def export(self, trace: Trace) -> None:
        raise NotImplementedError


class ConsoleExporter(Exporter):
    """打印到控制台 —— 开发/调试用。"""

    def export(self, trace: Trace) -> None:
        lines = [
            "",
            "=" * 60,
            f"Trace: {trace.trace_id}",
            f"输入: {trace.user_input[:100]}",
            f"总耗时: {trace.duration_ms:.0f}ms | Spans: {trace.span_count} | Tokens: {trace.total_tokens} | Errors: {trace.error_count}",
            "-" * 60,
        ]
        for s in trace.spans:
            icon = {"llm": "[LLM]", "tool": "[TOOL]", "guard": "[GUARD]"}.get(s.type.value, "?")
            status = "ERR" if s.error else "OK"
            parts = [f"  {icon} {s.name} | {s.duration_ms:.0f}ms | {status}"]
            if s.tokens:
                parts.append(f"tokens={s.tokens}")
            if s.error:
                parts.append(s.error[:60])
            lines.append(" | ".join(parts))
        lines.append(f"输出: {trace.final_output[:200]}")
        lines.append("=" * 60)
        print("\n".join(lines))


class LangFuseExporter(Exporter):
    """上报到 LangFuse 云端 —— 生产可观测。"""

    def __init__(
        self,
        secret_key: str | None = None,
        public_key: str | None = None,
        host: str | None = None,
    ):
        from dotenv import load_dotenv
        load_dotenv()

        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY", "")
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.host = host or os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")

        if not self.secret_key or not self.public_key:
            raise ValueError("LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY 未设置")

        from langfuse import Langfuse
        self._client = Langfuse(
            secret_key=self.secret_key,
            public_key=self.public_key,
            host=self.host,
        )

    def export(self, trace: Trace) -> None:
        as_type_map = {
            "llm": "generation",
            "tool": "tool",
            "guard": "guardrail",
        }

        # 根节点
        root = self._client.start_observation(
            name="agent-run",
            as_type="span",
            input=trace.user_input,
            output=trace.final_output,
        )

        for s in trace.spans:
            obs_type = as_type_map.get(s.type.value, "span")
            kwargs: dict = {
                "name": f"{s.type.value}: {s.name}",
                "as_type": obs_type,
                "input": s.input,
                "output": s.output,
            }
            if s.tokens:
                kwargs["usage_details"] = {"total_tokens": s.tokens}
            if s.model:
                kwargs["model"] = s.model
            if s.error:
                kwargs["level"] = "ERROR"
                kwargs["status_message"] = s.error[:100]
            child = self._client.start_observation(**kwargs)
            child.end()

        root.end()
        self._client.flush()
        print(f"[LangFuse] Trace {trace.trace_id} 已上报 → {self.host}")


# ============================================================
# Tracer
# ============================================================

class Tracer:
    """Agent 链路追踪器 —— 支持多 Exporter 同时输出。

    用法:
        tracer = Tracer([ConsoleExporter(), LangFuseExporter()])
        trace = tracer.start_trace("用户问题")

        with tracer.span("deepseek-chat", SpanType.LLM) as s:
            s.tokens = 150
            s.output = reply

        with tracer.span("calculator", SpanType.TOOL) as s:
            s.output = "21"

        tracer.finish_trace(trace, "最终回答")
    """

    def __init__(self, exporters: list[Exporter] | None = None):
        self.exporters = exporters or [ConsoleExporter()]
        self._current_trace: Trace | None = None

    def start_trace(self, user_input: str) -> Trace:
        import uuid
        self._current_trace = Trace(
            trace_id=uuid.uuid4().hex[:12],
            user_input=user_input,
            start_time=time.time(),
        )
        return self._current_trace

    def span(self, name: str, span_type: SpanType):
        return _SpanContext(self, name, span_type)

    def add_span(self, span: Span):
        if self._current_trace:
            self._current_trace.spans.append(span)

    def finish_trace(self, trace: Trace, final_output: str):
        trace.end_time = time.time()
        trace.final_output = final_output
        for exporter in self.exporters:
            try:
                exporter.export(trace)
            except Exception as e:
                print(f"[Tracer] Exporter {type(exporter).__name__} 失败: {e}")
        self._current_trace = None


class _SpanContext:
    """上下文管理器 —— 自动记录开始/结束时间。"""

    def __init__(self, tracer: Tracer, name: str, span_type: SpanType):
        self.tracer = tracer
        self.span = Span(type=span_type, name=name, start_time=time.time())

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.span.end_time = time.time()
        if exc_type:
            self.span.error = str(exc_val)
        self.tracer.add_span(self.span)
        return False
