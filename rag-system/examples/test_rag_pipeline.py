import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.embedder import Embedder
from rag_system.pipeline import RAGPipeline
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

DATA_DIR = str(Path(__file__).parent.parent / "data")

async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com"),
    )

    embedder = Embedder()
    rag = RAGPipeline(
        llm_client=client,
        llm_model="deepseek-chat",
        embedder=embedder,
    )

    # 入库
    rag.load_documents(DATA_DIR)

    # 测试提问
    questions = [
        "什么是 RAG？它的工作流程是什么？",
        "人工智能和机器学习有什么关系？",
    ]

    for q in questions:
        print(f"\n{'='*50}")
        print(f"Q: {q}")
        print(f"{'='*50}")
        answer = await rag.ask(q)
        print(f"A: {answer}")


if __name__ == "__main__":
    asyncio.run(main())