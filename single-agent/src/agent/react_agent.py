"""ReAct Agent —— Think → Act → Observe 循环。

教学点：
  1. ReAct 范式：不是一步回答，是 Thought → Action → Observation 循环
  2. Agent 自主决策：每次循环自己决定"调工具"还是"给出最终答案"
  3. System Prompt 驱动：整个循环靠 Prompt 约束行为
"""

import json
import re
from openai import AsyncOpenAI

from agent.tool_register import ToolRegistry


BASE_SYSTEM_PROMPT = """你是一个自主 Agent，可以调用工具回答问题。严格按以下格式响应：

当需要调用工具时：
Thought: [当前思考]
Action: [工具名称]
Action Input: [JSON 参数]

当有足够信息时：
Thought: [最终思考]
Final Answer: [中文回答]"""


class ReActAgent:
    """ReAct Agent """

    def __init__(self, client: AsyncOpenAI, model: str = 'deepseek-chat'):
        self.client = client
        self.model = model
        self.registry = ToolRegistry()
        self.history : list[dict] = []
    
    async def run(self, user_input: str, max_cycles: int = 5) -> str:
        if not self.history:
            system_prompt = self.registry.generate_system_prompt(BASE_SYSTEM_PROMPT)
            self.history.append({"role": "system", "content": system_prompt})
        self.history.append({"role": "user", "content": user_input})
        
        for _ in range(max_cycles):
            response = await self.client.chat.completions.create(
                model = self.model,
                messages = self.history,
            )
            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            print(f"Agent 第{_ + 1}轮 回复:\n{reply}\n{'-'*30}")

            # 判断是否给出final answer    
            if "Final Answer:" in reply:
                match  = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply
            
            # 解析 Action
            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if not action_match:
                self.history.append({"role": "user", "content": "请按格式输出：Thought/Action/Action Input 或 Final Answer"})
                continue

            tool_name = action_match.group(1)
            tool_args = json.loads(input_match.group(1)) if input_match else {}

            observation = self.registry.call(tool_name, **tool_args)

            print(f"observation:{observation}")
            self.history.append(
                {"role": "user", "content": f"Observation: {observation}"}
            )
        return "达到最大循环次数，未能给出最终答案。"