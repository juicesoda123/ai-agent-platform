"""真实环境测试 —— DeepSeek API + LangFuse 链路追踪。

运行前确认 .env 里三个值已填:
  DEEPSEEK_API_KEY=sk-...
  LANGFUSE_SECRET_KEY=sk-lf-...
  LANGFUSE_PUBLIC_KEY=pk-lf-...

运行:
  cd agent-platform && python examples/test_tracing_live.py

然后打开 https://us.cloud.langfuse.com 看 Trace。
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.tracing import (
    Tracer, SpanType, ConsoleExporter, LangFuseExporter,
)


def calculator(expression: str) -> str:
    expression = expression.replace("^", "**")
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "表达式包含非法字符"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"


async def main():
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    # 双出口：Console 打印 + LangFuse 上报
    tracer = Tracer([
        ConsoleExporter(),
        LangFuseExporter(),
    ])

    user_question = "7 的 3 次方加上 50 等于多少？"
    print(f"\nQ: {user_question}\n")

    trace = tracer.start_trace(user_question)

    # —— LLM Span ——
    with tracer.span("deepseek-chat", SpanType.LLM) as llm_span:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": """你是数学助手。需要计算时，在 Action Input 中直接写完整的数学表达式并一次算完。
严格按格式输出，只能包含一个 Action：

Action: calculator
Action Input: {"expression": "完整数学表达式"}

或直接给答案：
Final Answer: [回答]"""},
                {"role": "user", "content": user_question},
            ],
            temperature=0,  # 确定性输出，防止多步思维
        )
        reply = response.choices[0].message.content
        usage = response.usage

        llm_span.tokens = usage.total_tokens if usage else 0
        llm_span.model = "deepseek-chat"
        llm_span.input = user_question
        llm_span.output = reply

    print(f"LLM 回复:\n{reply}\n")

    # —— Tool Span ——
    import re, json
    action = re.search(r"Action:\s*(\w+)", reply)
    final_answer = reply

    if action:
        tool_name = action.group(1)
        input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)
        args = json.loads(input_match.group(1)) if input_match else {}

        with tracer.span(tool_name, SpanType.TOOL) as tool_span:
            tool_span.input = args
            result = calculator(**args)
            tool_span.output = result

        print(f"工具 [{tool_name}] 结果: {result}\n")

        # 第二轮 LLM：汇总结果
        with tracer.span("deepseek-chat", SpanType.LLM) as llm_span2:
            response2 = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "根据工具执行结果，用中文给用户最终回答。"},
                    {"role": "user", "content": f"问题: {user_question}\n工具结果: {result}\n请给出 Final Answer。"},
                ],
            )
            final_answer = response2.choices[0].message.content
            usage2 = response2.usage

            llm_span2.tokens = usage2.total_tokens if usage2 else 0
            llm_span2.model = "deepseek-chat"
            llm_span2.output = final_answer

    tracer.finish_trace(trace, final_answer)
    print(f"Final Answer: {final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
