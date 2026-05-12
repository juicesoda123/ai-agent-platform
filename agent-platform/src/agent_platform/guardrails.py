"""Guardrails 安全护栏 —— 输入净化 / 输出过滤 / 工具管控。

三层防护链：
  用户输入 → InputGuard → Agent(LLM+工具) → OutputGuard → 用户可见
                                ↓
                           ToolGuard (工具调用前拦截)
"""

import re
from typing import Any, Callable, NamedTuple


class GuardResult(NamedTuple):
    passed: bool
    data: str
    reason: str


# ============================================================
# InputGuard —— 输入层
# ============================================================

JAILBREAK_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|above)\s+instructions?|ignore\s+all\s+instructions?", "尝试覆盖系统指令"),
    (r"(you\s+are|act\s+as|pretend\s+to\s+be|roleplay\s+as)\s+(DAN|jailbreak|evil|unethical)", "角色扮演越狱"),
    (r"(DAN\s*mode|Developer\s*Mode|God\s*Mode)", "DAN/开发者模式"),
    (r"(what\s+is\s+your\s+system\s+prompt|reveal\s+your\s+instructions)", "尝试泄露系统 Prompt"),
    (r"(bypass|override|disable)\s+(safety|filter|restriction|guardrail)", "尝试绕过安全机制"),
    (r"do\s+not\s+(refuse|reject|deny)", "预阻止拒绝响应"),
    (r"(write|generate|create)\s+(malware|virus|exploit|ransomware)", "生成恶意代码"),
    (r"从\s*现在\s*开始.*(角色|身份|人格)", "中文角色越狱"),
]


class InputGuard:
    """输入护栏 —— 防注入、防越狱。"""

    def __init__(
        self,
        max_length: int = 2000,
        patterns: list[tuple[str, str]] | None = None,
    ):
        self.max_length = max_length
        self._patterns = [(re.compile(p, re.IGNORECASE), label)
                          for p, label in (patterns or JAILBREAK_PATTERNS)]

    def check(self, text: str) -> GuardResult:
        if len(text) > self.max_length:
            return GuardResult(False, text[:self.max_length],
                               f"输入过长 ({len(text)} > {self.max_length})")
        for regex, label in self._patterns:
            if regex.search(text):
                return GuardResult(False, text, f"检测到风险: {label}")
        return GuardResult(True, text, "")


# ============================================================
# OutputGuard —— 输出层
# ============================================================

SENSITIVE_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,60}", "API Key", "sk-***"),
    (r"1[3-9]\d{9}", "手机号", lambda m: m[:3] + "****" + m[-4:]),
    (r"\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]", "身份证号", "****"),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱", lambda m: m[0] + "***@" + m.split("@")[1] if "@" in m else "***"),
]


class OutputGuard:
    """输出护栏 —— 防敏感信息泄露。"""

    ACTION_REDACT = "redact"
    ACTION_BLOCK = "block"

    def __init__(self, action: str = ACTION_REDACT):
        if action not in (self.ACTION_REDACT, self.ACTION_BLOCK):
            raise ValueError(f"action 必须是 '{self.ACTION_REDACT}' 或 '{self.ACTION_BLOCK}'")
        self.action = action

    def check(self, text: str) -> GuardResult:
        violations = []
        result = text
        for pattern, label, replacement in SENSITIVE_PATTERNS:
            match = re.search(pattern, result)
            if match:
                violations.append(label)
                if self.action == self.ACTION_REDACT:
                    repl = replacement(match.group()) if callable(replacement) else replacement
                    result = re.sub(pattern, repl, result, count=1)
                else:
                    return GuardResult(False, text, f"检测到敏感信息: {label}")
        if violations:
            return GuardResult(True, result, f"已脱敏: {', '.join(violations)}")
        return GuardResult(True, text, "")


# ============================================================
# ToolGuard —— 工具层
# ============================================================

class ToolGuard:
    """工具调用护栏 —— 白名单 + 参数约束。"""

    def __init__(
        self,
        allowlist: set[str] | None = None,
        arg_constraints: dict[str, Callable[[dict], tuple[bool, str]]] | None = None,
    ):
        self.allowlist = allowlist or set()
        self.arg_constraints = arg_constraints or {}

    def check(self, tool_name: str, arguments: dict) -> GuardResult:
        if self.allowlist and tool_name not in self.allowlist:
            return GuardResult(False, str(arguments),
                               f"工具 '{tool_name}' 不在白名单内")
        constraint = self.arg_constraints.get(tool_name)
        if constraint:
            ok, reason = constraint(arguments)
            if not ok:
                return GuardResult(False, str(arguments), reason)
        return GuardResult(True, str(arguments), "")


# ============================================================
# GuardrailRunner —— 组合器
# ============================================================

class GuardrailRunner:
    """链式执行多个 Guard，第一个失败即短路。"""

    def __init__(self):
        self._input_guards: list[InputGuard] = []
        self._output_guards: list[OutputGuard] = []
        self._tool_guards: list[ToolGuard] = []

    def add_input(self, guard: InputGuard):
        self._input_guards.append(guard)

    def add_output(self, guard: OutputGuard):
        self._output_guards.append(guard)

    def add_tool(self, guard: ToolGuard):
        self._tool_guards.append(guard)

    def run_input(self, text: str) -> GuardResult:
        for g in self._input_guards:
            r = g.check(text)
            if not r.passed:
                return r
        return GuardResult(True, text, "")

    def run_output(self, text: str) -> GuardResult:
        current = text
        reasons = []
        for g in self._output_guards:
            r = g.check(current)
            if not r.passed:
                return r
            current = r.data
            if r.reason:
                reasons.append(r.reason)
        return GuardResult(True, current, "; ".join(reasons))

    def run_tool(self, name: str, args: dict) -> GuardResult:
        for g in self._tool_guards:
            r = g.check(name, args)
            if not r.passed:
                return r
        return GuardResult(True, str(args), "")
