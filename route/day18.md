# Day 18 — RAG 生成层：检索 + LLM 生成回答

> Phase 3：RAG 系统  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 把检索结果拼成 Prompt 喂给 LLM
2. 实现完整的 RAG 问答闭环：提问 → 检索 → 拼 context → LLM 生成
3. 产出：`RAGPipeline` 类——一条 `ask()` 走完全程

---

## 一、概念对齐：RAG 的 Prompt 怎么拼

```
用户问题: "什么是 RAG？"
    ↓
[向量检索]  →  Top-3 相关文档
    ↓
拼 Prompt:
  "根据以下参考资料回答问题。如果资料中没有相关信息，请如实说不知道。

   参考资料：
   [文档1] RAG 是一种检索增强生成技术...
   [文档2] RAG 的工作流程包括...

   问题：什么是 RAG？"
    ↓
[LLM 生成]  →  "RAG（检索增强生成）是一种将信息检索与文本生成结合的 AI 技术..."
```

---

## 二、动手实战（30 分钟）

### 任务 1：创建 `pipeline.py`

在 `src/rag_system/pipeline.py`：

```python
"""RAG Pipeline——串联检索 + 生成。"""

from rag_system.loader import DocumentLoader, Document
from rag_system.chunker import TextChunker
from rag_system.embedder import Embedder
from rag_system.vector_store import VectorStore
from openai import AsyncOpenAI


class RAGPipeline:
    """完整的 RAG 问答管道。"""

    def __init__(
        self,
        llm_client: AsyncOpenAI,
        llm_model: str,
        embedder: Embedder,
    ):
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.embedder = embedder
        self.store = VectorStore(embedder)

    def load_documents(self, directory: str, chunk_size: int = 500, chunk_overlap: int = 100) -> None:
        """加载文档并入库。"""
        loader = DocumentLoader(directory)
        documents = loader.load_all()
        if not documents:
            print("未找到任何文档")
            return

        chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = chunker.chunk(documents)
        self.store.add_documents(chunks)
        print(f"共入库 {self.store.count()} 个文档块")

    async def ask(self, question: str, top_k: int = 3) -> str:
        """提问 → 检索 → 拼 Prompt → LLM 生成回答。"""
        # 1. 检索相关文档
        results = self.store.query(question, top_k=top_k)
        if not results:
            return "未找到相关文档，无法回答该问题。"

        # 2. 拼 context
        context_parts = []
        for i, doc in enumerate(results):
            src = doc.metadata.get("source", "?")
            context_parts.append(f"[参考资料{i+1}，来源: {src}]\n{doc.content}")

        context = "\n\n".join(context_parts)

        # 3. 构造 Prompt
        prompt = f"""根据以下参考资料回答问题。如果资料中没有相关信息，请如实说不知道。

{context}

问题：{question}

请用中文回答，并在回答末尾注明参考了哪份资料。"""

        # 4. 调 LLM
        response = await self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": "你是基于 RAG 知识库的问答助手。"},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
```

### 任务 2：验证脚本

在 `examples/test_rag_pipeline.py`：

```python
"""验证 RAG 完整链路：提问 → 检索 → 生成。"""
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
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
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
```

运行：

```bash
cd rag-system && python examples/test_rag_pipeline.py
```

---

## 三、验收标准

- "什么是 RAG" → LLM 基于 `sample.md` 回答，内容准确，注明来源
- "人工智能和机器学习" → LLM 基于 `sample.txt` 回答
- 两个回答都引用了参考资料，不是瞎编的

---

## 四、RAG 完整链路（你现在拥有的）

```
D1  DocumentLoader   →  PDF / MD / TXT → Document
D2  TextChunker      →  Document → Chunks (overlap)
D3  Embedder         →  Text → [0.12, -0.34, ...]
D4  VectorStore      →  向量入库 + 相似度检索
D5  RAGPipeline      →  检索 + Prompt 拼装 + LLM 生成 = RAG 闭环
```
