"""验证 Plan-and-Execute —— 复杂多步任务。"""

import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent /"rag-system" / "src"))

from agent.plan_agent import PlanExecuteAgent
from agent.tool_register import ToolRegistry
from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import os

load_dotenv()

class CalcIn(BaseModel): expression: str = Field(description="数学表达式")
class SearchIn(BaseModel): query: str = Field(description="搜索关键词")

def calc(expression):
    expression = expression.replace("^", "**")
    if not all(c in set("0123456789+-*/().% ") for c in expression): return "bad"
    try: return str(eval(expression, {"__builtins__": {}}))
    except Exception as e: return f"err:{e}"

async def main():
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    embedder = Embedder()
    rag = RAGPipeline(llm_client=client, llm_model="deepseek-chat", embedder=embedder)
    rag.load_documents(str(Path(__file__).parent.parent.parent / "rag-system" / "data"))

    def search_rag(query):
        r = rag.store.query(query, top_k=2)
        return "\n".join([f"[{d.metadata.get('source','?')}] {d.content[:100]}" for d in r]) if r else "none"

    registry = ToolRegistry()
    registry.register("calculator", "数学计算", calc, CalcIn)
    registry.register("search_rag", "搜索知识库", search_rag, SearchIn)

    agent = PlanExecuteAgent(client, registry)

    # 复杂任务：需要搜索 + 计算
    q = "AI有哪些应用？机器学习又是什么？顺便算一下 2 的 10 次方。"
    print(f"Q: {q}\n")
    answer = await agent.run(q)
    print(f"\n>>> Final Answer:\n{answer}")


if __name__ == "__main__":
    asyncio.run(main())