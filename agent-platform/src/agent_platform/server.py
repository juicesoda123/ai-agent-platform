"""Agent HTTP 服务 —— FastAPI 封装，串接 Guardrails + Tracing + Cost。

启动:
    python -m agent_platform.server

端点:
    GET  /health             健康检查
    GET  /agent/tools        列出可用工具
    POST /agent/run          执行 Agent（非流式）
    POST /agent/run/stream   执行 Agent（SSE 流式）
    GET  /agent/cost         成本报告
"""

import os
import sys
import json
import re
import asyncio
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 确保 single-agent 模块可导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "single-agent" / "src"))

load_dotenv()


# ============================================================
# Pydantic 模型
# ============================================================

class AgentRequest(BaseModel):
    question: str = Field(..., description="用户问题", max_length=2000)
    max_cycles: int = Field(default=5, ge=1, le=10, description="最大推理轮数")
    model: str = Field(default="deepseek-chat", description="模型名")


class AgentResponse(BaseModel):
    success: bool
    answer: str
    trace_id: Optional[str] = None
    cost: Optional[float] = None       # RMB
    tokens: Optional[int] = None
    cycles: Optional[int] = None       # 推理轮数


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: str


class HealthResponse(BaseModel):
    status: str = "ok"
    model: str
    tools: list[str]
    daily_cost: float
    budget_remaining: float


# ============================================================
# Agent Server
# ============================================================

class AgentServer:
    """组装 Agent + 护栏 + 追踪 + 成本控制。"""

    def __init__(self, model: str = "deepseek-chat"):
        from openai import AsyncOpenAI
        from agent.tool_register import ToolRegistry
        from agent.react_agent import ReActAgent

        self.model = model

        # LLM 客户端
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

        # 工具注册
        self.registry = ToolRegistry()
        # calculator 工具
        from pydantic import BaseModel as PydanticBase, Field as PydanticField
        class CalcIn(PydanticBase):
            expression: str = PydanticField(description="数学表达式，如 3**5+100")
        self.registry.register("calculator", "数学计算", self._calc, CalcIn)

        # Agent
        self.agent = ReActAgent(self.client, model=model)

        # 护栏 + 追踪 + 成本（延迟初始化，避免导入时触发 LangFuse 连接）
        self._guard_runner = None
        self._tracer = None
        self._cost_tracker = None

    @staticmethod
    def _calc(expression: str) -> str:
        expression = expression.replace("^", "**")
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return "表达式包含非法字符"
        try:
            return str(eval(expression, {"__builtins__": {}}))
        except Exception as e:
            return f"计算错误: {e}"

    @property
    def guard_runner(self):
        if self._guard_runner is None:
            from agent_platform.guardrails import GuardrailRunner, InputGuard, OutputGuard
            self._guard_runner = GuardrailRunner()
            self._guard_runner.add_input(InputGuard(max_length=2000))
            self._guard_runner.add_output(OutputGuard(action="redact"))
        return self._guard_runner

    @property
    def tracer(self):
        if self._tracer is None:
            from agent_platform.tracing import Tracer, ConsoleExporter, LangFuseExporter
            exporters = [ConsoleExporter()]
            try:
                exporters.append(LangFuseExporter())
            except Exception:
                pass  # LangFuse 未配置时静默跳过
            self._tracer = Tracer(exporters)
        return self._tracer

    @property
    def cost_tracker(self):
        if self._cost_tracker is None:
            from agent_platform.cost import CostTracker
            self._cost_tracker = CostTracker(daily_budget=10.0)
        return self._cost_tracker

    def list_tools(self) -> list[dict]:
        return self.registry.list_tools()

    async def run(self, question: str, max_cycles: int = 5, model: str = "") -> AgentResponse:
        """执行一次 Agent 调用，含护栏 + 追踪 + 成本。"""
        model = model or self.model

        # --- 输入护栏 ---
        gr = self.guard_runner.run_input(question)
        if not gr.passed:
            return AgentResponse(success=False, answer=f"输入被拦截: {gr.reason}")

        # --- 追踪开始 ---
        trace = self.tracer.start_trace(question)
        cycles = 0

        try:
            # --- Agent 执行 ---
            response = await self.agent.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.agent.registry.generate_system_prompt(
                        "你是自主 Agent。用工具或直接回答。"
                        "\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [中文回答]"
                    )},
                    {"role": "user", "content": gr.data},
                ],
            )
            reply = response.choices[0].message.content
            usage = response.usage

            # LLM Span
            from agent_platform.tracing import SpanType
            with self.tracer.span(model, SpanType.LLM) as s:
                s.tokens = usage.total_tokens if usage else 0
                s.model = model
                s.output = reply

            cycles = 1

            # --- 工具调用 ---
            final_answer = reply
            action = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if action:
                tool_name = action.group(1)
                tool_args = json.loads(input_match.group(1)) if input_match else {}

                # 工具护栏
                tg = self.guard_runner.run_tool(tool_name, tool_args)
                if not tg.passed:
                    return AgentResponse(success=False, answer=f"工具被拦截: {tg.reason}")

                with self.tracer.span(tool_name, SpanType.TOOL) as ts:
                    ts.input = tool_args
                    result = self.registry.call(tool_name, **tool_args)
                    ts.output = result

                # 二轮汇总
                response2 = await self.agent.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "根据工具结果，用中文给用户最终回答。"},
                        {"role": "user", "content": f"问题: {question}\n工具结果: {result}\n请给出 Final Answer。"},
                    ],
                )
                final_answer = response2.choices[0].message.content
                usage2 = response2.usage

                with self.tracer.span(model, SpanType.LLM) as s2:
                    s2.tokens = usage2.total_tokens if usage2 else 0
                    s2.model = model
                    s2.output = final_answer

                cycles = 2

            # --- 输出护栏 + PII ---
            gr_out = self.guard_runner.run_output(final_answer)
            from agent_platform.pii import PIIScanner
            pii_result = PIIScanner().scan(gr_out.data)
            safe_answer = pii_result.sanitized

            # --- 成本记录 ---
            self.cost_tracker.record_from_spans(trace.spans)

            self.tracer.finish_trace(trace, safe_answer)

            return AgentResponse(
                success=True,
                answer=safe_answer,
                trace_id=trace.trace_id,
                cost=round(self.cost_tracker.daily_cost, 4),
                tokens=trace.total_tokens,
                cycles=cycles,
            )

        except Exception as e:
            self.tracer.finish_trace(trace, f"Error: {e}")
            return AgentResponse(success=False, answer=f"执行错误: {e}")


# ============================================================
# FastAPI 应用
# ============================================================

_agent_server: Optional[AgentServer] = None


def get_server() -> AgentServer:
    global _agent_server
    if _agent_server is None:
        _agent_server = AgentServer()
    return _agent_server


app = FastAPI(title="AI Agent Platform", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
async def health():
    srv = get_server()
    return HealthResponse(
        status="ok",
        model=srv.model,
        tools=[t["name"] for t in srv.list_tools()],
        daily_cost=round(srv.cost_tracker.daily_cost, 4),
        budget_remaining=round(srv.cost_tracker.daily_budget_remaining, 4),
    )


@app.get("/agent/tools", response_model=list[ToolInfo])
async def list_tools():
    srv = get_server()
    return [ToolInfo(**t) for t in srv.list_tools()]


@app.post("/agent/run", response_model=AgentResponse)
async def agent_run(req: AgentRequest):
    srv = get_server()
    return await srv.run(
        question=req.question,
        max_cycles=req.max_cycles,
        model=req.model,
    )


@app.post("/agent/run/stream")
async def agent_run_stream(req: AgentRequest):
    srv = get_server()

    async def event_stream():
        result = await srv.run(
            question=req.question,
            max_cycles=req.max_cycles,
            model=req.model,
        )
        yield f"data: {result.model_dump_json()}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/agent/cost")
async def agent_cost():
    srv = get_server()
    return {
        "report": srv.cost_tracker.report(),
        "daily_cost": srv.cost_tracker.daily_cost,
        "monthly_cost": srv.cost_tracker.monthly_cost,
        "total_tokens": srv.cost_tracker.total_tokens,
        "is_over_budget": srv.cost_tracker.is_over_budget,
        "recommend_model": srv.cost_tracker.recommend_model(),
    }


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent_platform.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
