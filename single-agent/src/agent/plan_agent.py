"""Plan-and-Execute Agent —— 先列计划再执行。

与 ReActAgent 的区别：
  ReAct: 每步只想"下一步做什么"
  PlanExecute: 先看全局，列出完整计划，再逐步执行
"""


import json
import re
from openai import AsyncOpenAI

PLANNER_PROMPT = """你是一个任务规划专家。用户会给你一个问题，你需要把它拆解成可执行的步骤。

输出格式：
Plan:
1. [工具名] 具体操作描述 (参数: key=value)
2. [工具名] 具体操作描述 (参数: key=value)
...

规则：
- 每步必须对应一个可用工具
- 步骤之间可以有依赖（后面步骤可以引用前面步骤的结果）
- 如果问题简单，可以用一个步骤完成"""

EXECUTOR_PROMPT = """你正在执行一个预设计划。根据当前步骤的 Observation，判断是否继续执行下一步。

如果所有步骤完成，给出 Final Answer。
如果还需要信息，指出下一步的 Action 和 Action Input。

格式（继续执行）：
Thought: [分析]
Action: [工具名]
Action Input: [JSON]

格式（全部完成）：
Thought: [最终分析]
Final Answer: [完整回答]"""

class PlanExecuteAgent:
    """先规划再执行"""

    def __init__(self, client: AsyncOpenAI, registry):
        self.client = client
        self.registry = registry
    
    async def run(self, user_input: str, max_steps: int = 5) -> str:
        # 1. 制定计划
        tool_desc = self.registry.list_tools()
        plan_prompt = PLANNER_PROMPT + f"\n\n可用工具：{json.dumps(tool_desc, ensure_ascii=False, indent=2)}"

        plan_response = await self.client.chat.completions.create(
            model = 'deepseek-chat',
            messages = [
                {"role": "system", "content": plan_prompt},
                {"role": "user", "content": f"请为以下问题制定执行计划：{user_input}"},
            ],
        )
        plan_text = plan_response.choices[0].message.content
        print(f"制定的计划:\n{plan_text}\n{'='*30}")
        # 解析计划
        plan_steps = re.findall(r"\d+\.\s*(\w+)", plan_text)

        # 2. 执行计划
        context = [] # 收集每步结果
        messages = [{"role": "system", "content": EXECUTOR_PROMPT},
                    {"role": "user", "content": f"问题: {user_input}\n计划:\n{plan_text}"}]
        
        for step_idx in range(min(len(plan_steps), max_steps)):
            response = await self.client.chat.completions.create(
                model = 'deepseek-chat',
                messages = messages,
            )
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})
            print(f"执行步骤 {step_idx + 1} 回复:\n{reply}\n{'-'*30}")

            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply
            
            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if not action_match:
                break

            tool_name = action_match.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}
            observation = self.registry.call(tool_name, **tool_args)

            context.append(f"Step {step_idx + 1} 结果: {observation}")
            print(f"Observation: {observation[:200]}\n")
            messages.append({"role": "user", "content": f"Observation: {observation}"})

            # ——— Phase 3: 汇总 ———
        context_str = "\n".join(context)
        summary_response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "根据以下执行结果，用中文给用户一个完整回答。"},
                {"role": "user", "content": f"问题：{user_input}\n\n执行结果：\n{context_str}\n\n请给出 Final Answer。"},
            ],
        )
        return summary_response.choices[0].message.content
        
