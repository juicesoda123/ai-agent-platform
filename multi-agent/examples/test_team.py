"""验证 Multi-Agent 协作。"""
import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-system" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "single-agent" / "src"))

from multi_agent.base import BaseAgent
from multi_agent.supervisor import Supervisor
from agent.tool_register import ToolRegistry
from pydantic import BaseModel, Field
from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


class CalcIn(BaseModel): expression: str = Field(description="数学表达式")
class SearchIn(BaseModel): query: str = Field(description="搜索关键词")

def calc(expression):
    expression = expression.replace("^", "**")
    try: 
        return str(eval(expression, {"__builtins__": {}}))
    except Exception:
        return "计算错误"

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

    # 创建三个专才 Agent
    researcher_reg = ToolRegistry()
    researcher_reg.register("search_rag", "搜索知识库", search_rag, SearchIn)
    researcher = BaseAgent("Researcher", "信息检索专家，负责搜索和整理信息", client, researcher_reg)

    coder_reg = ToolRegistry()
    coder_reg.register("calculator", "数学计算", calc, CalcIn)
    coder = BaseAgent("Coder", "编程和数学专家，负责写代码和计算", client, coder_reg)

    reviewer = BaseAgent("Reviewer", "质量审查专家，负责检查结果的正确性", client, ToolRegistry())

    supervisor = Supervisor(client)
    supervisor.register(researcher)
    supervisor.register(coder)
    supervisor.register(reviewer)

    q = "搜索一下什么是RAG，然后帮我写一个判断质数的Python函数，最后计算2^10"
    print(f"Q: {q}\n")
    answer = await supervisor.run(q)
    print(f"\n{'='*60}")
    print(f"Final Answer:\n{answer}")


if __name__ == "__main__":
    asyncio.run(main())