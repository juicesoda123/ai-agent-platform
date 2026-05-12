"""验证 Tracing 可观测性 —— 纯逻辑测试，不需要 API Key。"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.tracing import (
    Tracer, Trace, Span, SpanType,
    ConsoleExporter, Exporter,
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
# 1. Span 基础属性
# ============================================================
print("=== 1. Span 基础 ===")

s = Span(type=SpanType.LLM, name="deepseek-chat", start_time=time.time())
time.sleep(0.01)
s.end_time = time.time()
s.tokens = 150
s.model = "deepseek-chat"
s.input = "你好"
s.output = "你好！有什么可以帮助你的？"

test("duration_ms > 0", s.duration_ms > 0, f"{s.duration_ms}ms")
test("tokens 记录", s.tokens == 150)
test("to_dict 含 type", "llm" in str(s.to_dict()))
test("to_dict 含 tokens", "150" in str(s.to_dict()))
test("error 为空时不输出 error", s.to_dict()["error"] == "")


# ============================================================
# 2. Trace 结构
# ============================================================
print("\n=== 2. Trace 结构 ===")

t = Trace(trace_id="test-001", user_input="1+1等于几", start_time=time.time())
s1 = Span(type=SpanType.LLM, name="deepseek-chat", start_time=time.time(), end_time=time.time(), tokens=100)
s2 = Span(type=SpanType.TOOL, name="calculator", start_time=time.time(), end_time=time.time())
s3 = Span(type=SpanType.GUARD, name="InputGuard", start_time=time.time(), end_time=time.time(), error="检测到风险")
t.spans = [s1, s2, s3]
t.end_time = time.time()
t.final_output = "1+1等于2"

test("span_count", t.span_count == 3)
test("total_tokens", t.total_tokens == 100)
test("error_count", t.error_count == 1)
test("duration_ms", t.duration_ms >= 0)


# ============================================================
# 3. Tracer + ConsoleExporter
# ============================================================
print("\n=== 3. Tracer 完整流程 ===")

class TestExporter(Exporter):
    """收集最后一次 export 的参数，用于断言。"""
    def __init__(self):
        self.last_trace = None

    def export(self, trace: Trace):
        self.last_trace = trace

exporter = TestExporter()
tracer = Tracer(exporter)

# start_trace
trace = tracer.start_trace("帮我算一下 3*7")
test("trace_id 不为空", len(trace.trace_id) == 12, trace.trace_id)
test("user_input 记录", trace.user_input == "帮我算一下 3*7")

# LLM span
with tracer.span("deepseek-chat", SpanType.LLM) as s:
    time.sleep(0.01)
    s.tokens = 80
    s.model = "deepseek-chat"
    s.input = "帮我算一下 3*7"
    s.output = 'Action: calculator\nAction Input: {"expression":"3*7"}'

llm_span = trace.spans[-1]
test("LLM span 记录", llm_span.type == SpanType.LLM and llm_span.name == "deepseek-chat")
test("LLM span tokens", llm_span.tokens == 80)
test("LLM span duration", llm_span.duration_ms > 0, f"{llm_span.duration_ms:.1f}ms")

# Tool span
with tracer.span("calculator", SpanType.TOOL) as s:
    time.sleep(0.005)
    s.input = {"expression": "3*7"}
    s.output = "21"

tool_span = trace.spans[-1]
test("Tool span 记录", tool_span.type == SpanType.TOOL)
test("Tool span input", "3*7" in str(tool_span.input))

# Guard span
with tracer.span("InputGuard", SpanType.GUARD) as s:
    s.metadata = {"passed": True}

guard_span = trace.spans[-1]
test("Guard span 记录", guard_span.type == SpanType.GUARD)
test("Guard span metadata", guard_span.metadata.get("passed") == True)

# finish_trace
tracer.finish_trace(trace, "3*7=21")
test("trace 已导出", exporter.last_trace is not None)
test("final_output 记录", exporter.last_trace.final_output == "3*7=21")
test("spans 都记录", exporter.last_trace.span_count == 3)

# ============================================================
# 4. 异常捕获
# ============================================================
print("\n=== 4. 异常捕获 ===")

exporter2 = TestExporter()
tracer2 = Tracer(exporter2)
trace2 = tracer2.start_trace("test error")

try:
    with tracer2.span("risky_tool", SpanType.TOOL) as s:
        raise ValueError("工具执行失败")
except ValueError:
    pass  # 异常继续往上抛，但 span 记录了 error

error_span = trace2.spans[-1]
test("异常被 span 记录", error_span.error != "")
test("异常信息正确", "工具执行失败" in error_span.error)

tracer2.finish_trace(trace2, "error handled")
test("trace error_count", exporter2.last_trace.error_count == 1)


# ============================================================
# 5. ConsoleExporter 输出验证
# ============================================================
print("\n=== 5. ConsoleExporter === (以下为实际输出)")

tracer3 = Tracer(ConsoleExporter())
trace3 = tracer3.start_trace("测试控制台输出")
with tracer3.span("test-model", SpanType.LLM) as s:
    s.tokens = 42
    s.output = "test response"
with tracer3.span("test-tool", SpanType.TOOL) as s:
    s.output = "result"
tracer3.finish_trace(trace3, "最终结果")

# ConsoleExporter 已经打印到终端了，确认不崩
test("ConsoleExporter 不抛异常", True)


# ============================================================
print(f"\n{'='*40}")
print(f"RESULTS: {passed} passed, {failed} failed (total {passed + failed})")
print(f"{'ALL PASSED' if failed == 0 else 'SOME FAILED'}")
