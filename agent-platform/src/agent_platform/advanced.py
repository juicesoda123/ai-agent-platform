"""Agent 高级策略 —— Reflexion 反思 + 多路生成。"""

import re
import json
import asyncio


async def reflexion_answer(client, registry, question: str, max_cycles: int = 4, temperature: float = 0.0) -> dict:
    """Reflexion: 回答 → 自我批判 → 修正 → 返回改进版。

    返回:
        {"answer": 最终答案, "draft": 初稿, "critique": 自我批判, "steps": [...], "tokens": int}
    """
    system_prompt = registry.generate_system_prompt(
        "你是严谨的研究助手。基于工具结果回答，不编造。"
        "\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [中文回答]"
    )
    msgs = [{"role":"system","content":system_prompt},{"role":"user","content":question}]
    steps=[]; total=0

    # 第一轮：生成初稿
    for _ in range(max_cycles):
        r = await client.chat.completions.create(model="deepseek-chat",messages=msgs,max_tokens=4096,temperature=temperature)
        reply = r.choices[0].message.content
        if r.usage: total+=r.usage.total_tokens
        msgs.append({"role":"assistant","content":reply})

        if "Final Answer:" in reply:
            m = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
            draft = m.group(1).strip() if m else reply
            break

        action=re.search(r"Action:\s*(\w+)",reply)
        inp=re.search(r"Action Input:\s*(\{.*\})",reply,re.DOTALL)
        if action:
            tn=action.group(1)
            try: args=json.loads(inp.group(1)) if inp else {}
            except: args={}
            try:
                obs=registry.call(tn,**args)
            except Exception as e:
                obs=f"工具调用失败:{e},请换工具或直接回答。"
            steps.append({"tool":tn,"args":str(args)[:100],"result":obs[:300]})
            msgs.append({"role":"user","content":f"Observation:\n{obs}"})
        else:
            draft=reply; break
    else:
        draft = "无法在循环内完成回答"

    # 第二轮：自我批判
    critique_prompt = f"""请严格审查以下回答的质量：

原始问题：{question}

回答：
{draft}

检查清单：
1. 事实是否正确？（如果有来源引用，逐条验证）
2. 逻辑是否完整？（有没有遗漏关键信息）
3. 表达是否清晰？（中文是否流畅）

请用以下格式输出：
Critique: [你的批判意见，逐条列出问题]
Score: [1-10分]"""

    cr = await client.chat.completions.create(
        model="deepseek-chat",max_tokens=4096,temperature=temperature,
        messages=[{"role":"user","content":critique_prompt}],
    )
    critique = cr.choices[0].message.content
    if cr.usage: total+=cr.usage.total_tokens

    # 第三轮：修正
    revise_prompt = f"""根据以下批判意见修正你的回答。

批判意见：
{critique}

请输出修正后的最终答案：
Final Answer: [修正后的中文回答，引用来源]"""

    fr = await client.chat.completions.create(
        model="deepseek-chat",max_tokens=4096,
        messages=[{"role":"user","content":revise_prompt}],
    )
    final_reply = fr.choices[0].message.content
    if fr.usage: total+=fr.usage.total_tokens

    m = re.search(r"Final Answer:\s*(.*)", final_reply, re.DOTALL)
    final = m.group(1).strip() if m else final_reply

    return {"answer":final,"draft":draft,"critique":critique,"steps":steps,"tokens":total}


async def multi_path_answer(client, registry, question: str, max_cycles: int = 4, temperature: float = 0.0) -> list[dict]:
    """多路生成：3 种风格独立回答，用户选择。

    返回 3 个答案，每个带标签：简洁 / 详细 / 代码实操
    """
    styles = [
        ("简洁", "用最精炼的语言回答，不超过 200 字。", max_cycles),
        ("详细", "给出全面深入的回答，包含背景、原理、步骤。", max_cycles),
        ("代码", "如果涉及编程，一定要给出完整可运行的代码。代码必须完整，不能省略或截断，确保复制即可运行。", max_cycles + 2),
    ]

    results = []
    for label, style, cycles in styles:
        sp = registry.generate_system_prompt(
            f"你是 AI 助手。回答风格：{style}"
            "\nAction: [工具名]\nAction Input: [JSON参数]\n或 Final Answer: [回答]"
        )
        msgs = [{"role":"system","content":sp},{"role":"user","content":question}]
        tokens=0; answer=""; steps=[]

        for _ in range(cycles):
            r = await client.chat.completions.create(model="deepseek-chat",messages=msgs,max_tokens=4096,temperature=temperature)
            reply = r.choices[0].message.content
            if r.usage: tokens+=r.usage.total_tokens
            msgs.append({"role":"assistant","content":reply})

            if "Final Answer:" in reply:
                m = re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)
                answer = m.group(1).strip() if m else reply
                break

            action=re.search(r"Action:\s*(\w+)",reply)
            inp=re.search(r"Action Input:\s*(\{.*\})",reply,re.DOTALL)
            if action:
                tn=action.group(1)
                try: args=json.loads(inp.group(1)) if inp else {}
                except: args={}
                try:
                    obs=registry.call(tn,**args)
                except Exception as e:
                    obs=f"工具调用失败:{e},请换工具或直接回答。"
                steps.append({"tool":tn,"result":obs[:200]})
                msgs.append({"role":"user","content":f"Observation:\n{obs}"})
            else:
                answer=reply; break
        else:
            answer="无法在循环内完成"

        results.append({"label":label,"answer":answer,"tokens":tokens,"steps":steps})

    return results
