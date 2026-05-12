"""Agent 引擎 —— UI 和 API 共享的核心推理逻辑。

解决 ui.py 和 server.py 各自重复实现 Agent 循环的问题。
"""

import re, json, sys, asyncio
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "single-agent" / "src"))
from agent.tool_register import ToolRegistry


class AgentEngine:
    """共享 Agent 执行引擎。"""

    def __init__(self, client, registry: ToolRegistry):
        self.client = client
        self.registry = registry

    async def run(
        self,
        question: str,
        model: str = "deepseek-chat",
        max_cycles: int = 6,
        system_prompt: str = "",
        stream_callback=None,
    ) -> dict:
        """执行 Agent 循环。

        Args:
            question: 用户问题
            model: 模型名
            max_cycles: 最大推理轮数
            system_prompt: 系统提示词
            stream_callback: 可选，每收到 LLM chunk 就回调 (text_chunk)

        Returns:
            {"answer": str, "steps": [...], "tokens": int, "tools": [...], "sources": [...]}
        """
        if not system_prompt:
            system_prompt = self.registry.generate_system_prompt(
                "你是 AI 助手。\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [中文回答]"
            )

        msgs = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": question}]
        steps = []
        tools_used = []
        total_tokens = 0
        sources = []
        called_sigs = set()
        final = None

        for cycle in range(max_cycles):
            resp = await self.client.chat.completions.create(
                model=model, messages=msgs, max_tokens=4096,
            )
            reply = resp.choices[0].message.content
            if resp.usage: total_tokens += resp.usage.total_tokens
            msgs.append({"role": "assistant", "content": reply})

            if "Final Answer:" in reply:
                m = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                final = m.group(1).strip() if m else reply
                break

            action = re.search(r"Action:\s*(\w+)", reply)
            inp = re.search(r"Action Input:\s*(\{.*?\})\s*$", reply, re.DOTALL)
            if not inp:
                inp = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)

            if action:
                tn = action.group(1)
                try:
                    args = json.loads(inp.group(1)) if inp else {}
                except Exception:
                    args = {}
                step = {"thought": reply[:250], "tool": tn, "args": str(args)[:120]}
                sig = f"{tn}|{json.dumps(args, sort_keys=True)}"
                if sig in called_sigs:
                    observation = "警告:此工具+参数刚调用过，请勿重复。如信息足够请立即 Final Answer。"
                else:
                    called_sigs.add(sig)
                    try:
                        observation = self.registry.call(tn, **args)
                    except Exception as e:
                        observation = f"工具调用失败: {e}。请换工具或直接回答。"
                tools_used.append(tn)
                step["result"] = observation[:500]
                # 提取 URL
                urls = re.findall(r"https?://[^\s\"\)]+", observation)
                for u in urls[:3]:
                    if u not in [s["url"] for s in sources]:
                        sources.append({"tool": tn, "url": u})
                steps.append(step)
                obs_text = f"Observation:\n{observation}"
                n = len(steps)
                if n >= 3:
                    obs_text += f"\n\n[系统提示]已调用{n}次工具，请立即输出 Final Answer。"
                msgs.append({"role": "user", "content": obs_text})
            else:
                final = reply
                break

        if final is None:
            final = "循环超限，请简化问题重试。"

        return {
            "answer": final,
            "steps": steps,
            "tokens": total_tokens,
            "tools": tools_used,
            "sources": sources,
        }

    async def stream_final(self, model: str, messages: list[dict]):
        """流式生成最终答案（用于 write_stream）。"""
        stream = await self.client.chat.completions.create(
            model=model, messages=messages, stream=True, max_tokens=4096,
        )
        collected = ""
        async for chunk in stream:
            c = chunk.choices[0].delta.content or ""
            collected += c
            if collected.startswith("Final Answer:"):
                if len(collected) > 13:
                    yield collected[13:].lstrip()
            elif len(collected) > 10:
                yield c
