import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent /"rag-system" / "src"))

from agent.react_agent import ReActAgent
from openai import AsyncOpenAI
from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field

load_dotenv()

DATA_DIR = str(Path(__file__).parent.parent.parent / "rag-system" / "data")

class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，如 3**5+100")

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")

def calculator(expression: str) -> str:
    expression = expression.replace("^", "**")
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "表达式包含非法字符！"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"

async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com"),
    )

    # 初始化真RAG
    embedder = Embedder()
    rag = RAGPipeline(
        llm_client=client,
        llm_model="deepseek-chat",
        embedder=embedder,
    )
    rag.load_documents(DATA_DIR)

    # 用RAG的ask方法作为搜索工具，这里只检索，不LLM生成
    def search_rag(query: str) -> str:
        results = rag.store.query(query, top_k=3)
        if not results:
            return "没有找到相关信息。"
        parts = []
        for i, doc in enumerate(results):
            src = doc.metadata.get("source", "?")
            parts.append(f"结果 {i+1} (来源: {src}):\n{doc.content[:200]}\n")
        return "\n".join(parts)
    
    agent = ReActAgent(client)
    agent.registry.register("calculator", "执行数学计算", calculator, CalculatorInput)
    agent.registry.register("search_rag", "搜索知识库文档", search_rag, SearchInput)

    print("=" * 60)
    print("AI Agent 已就绪。输入 /quit 退出。")
    print("=" * 60)

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "/quit":
            print("再见！")
            break
        answer = await agent.run(user_input, max_cycles=5)
        print(f"AI Agent: {answer}\n")

if __name__ == "__main__":
    asyncio.run(main())

