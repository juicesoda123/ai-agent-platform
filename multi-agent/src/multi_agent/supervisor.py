"""Supervisor —— 拆任务、分发给专才、汇总结果。"""

import json, re
from openai import AsyncOpenAI

SUPERVISOR_PROMPT = """你是一个团队主管(Supervisor)。你有以下成员可以调遣：

{team_roster}

用户给你一个任务后，你需要：
1. 分析任务需要哪些成员参与
2. 把子任务分配给对应成员
3. 收集所有成员的结果后汇总

输出格式：
Plan: 列出需要哪些成员、各自做什么
Assignments: [{{"agent": "成员名", "task": "子任务描述"}}, ...]

收到所有结果后输出：
Final Summary: [给用户的最终交付]"""


class Supervisor:
    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self.agents: dict = {}  # name -> BaseAgent

    def register(self, agent) -> None:
        self.agents[agent.name] = agent

    async def run(self, user_input: str) -> str:
        team_desc = "\n".join(f"- {a.name}: {a.role}" for a in self.agents.values())
        prompt = SUPERVISOR_PROMPT.replace("{team_roster}", team_desc)

        # 1. 制定分工计划
        response = await self.client.chat.completions.create(
            model = "deepseek-chat",
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"任务：{user_input}\n请制定计划并分配任务。"},
            ],
        )
        plan = response.choices[0].message.content
        print(f"Supervisor Plan:\n{plan}")

        # 2. 解析任务分配（从 Assignments JSON 提取）
        results = {}
        assignments = self._parse_assignments(plan)
        for name, agent in self.agents.items():
            task = assignments.get(name, user_input)  # 没分配到就用原始问题
            print(f"--- 调度 {name} ---\n任务: {task[:100]}")
            result = await agent.execute(task)
            results[name] = result
            print(f"结果: {result[:200]}\n")

        # 3. 汇总结果
        context = "\n".join(f"{name} 的结果: {res}" for name, res in results.items())
        summary_response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是团队主管，请汇总以下成员的工作成果，给用户一个完整且有条理的 Final Answer。"},
                {"role": "user", "content": f"原始任务：{user_input}\n成员成果：\n{context}"},
            ],
        )
        return summary_response.choices[0].message.content
    
    def _parse_assignments(self, plan: str) -> dict[str, str]:
        """从 Assignments JSON 中解析任务分配。"""
        import re
        match = re.search(r"Assignments:\s*(\[.*?\])", plan, re.DOTALL)
        if not match:
            return {}
        try:
            items = json.loads(match.group(1))
            return {item["agent"]: item["task"] for item in items}
        except (json.JSONDecodeError, KeyError):
            return {}