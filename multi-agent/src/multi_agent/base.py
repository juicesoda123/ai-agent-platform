"""Base Agent —— 所有角色 Agent 的基类。"""

import re, json
from openai import AsyncOpenAI

class BaseAgent:
    """Base Agent —— 所有角色 Agent 的基类。"""
    def __init__(
        self,
        name: str,
        role: str,
        client: AsyncOpenAI,
        registry,
    ):
        self.name = name
        self.role = role
        self.client = client
        self.registry = registry
    
    async def execute(self, task: str, max_cycles: int = 5) -> str:
        """执行一个子任务，返回结果"""
        system_prompt = f"""你是 {self.name}，角色是 {self.role}。

{self.registry.generate_system_prompt("你可以使用以下工具：")}

严格按格式：
Action: [工具名]
Action Input: [JSON参数]

或任务完成时：
Final Answer: [你的交付]"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]
        
        for _ in range(max_cycles):
            response = await self.client.chat.completions.create(
                model = "deepseek-chat",
                messages = messages,
            )    
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})

            if "Final Answer:" in reply:
                match = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                return match.group(1).strip() if match else reply
            action_match = re.search(r"Action:\s*(\w+)", reply)
            input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)
            if action_match:
                tool_name = action_match.group(1)
                tool_args = json.loads(input_match.group(1)) if input_match else {}
                observation = self.registry.call(tool_name, **tool_args)
                messages.append({"role": "user", "content": f"Observation: {observation}"})

        return f"{self.name} 未能在规定的交互轮数内完成任务。" 
            