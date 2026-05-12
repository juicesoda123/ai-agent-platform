# Day 17 — ChromaDB：向量存储与检索

> Phase 3：RAG 系统  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解向量数据库的作用——存向量 + 按相似度检索
2. 学会 ChromaDB 的基本 CRUD
3. 把 D1(DocumentLoader) + D2(TextChunker) + D3(Embedder) 串成一条完整链路
4. 产出：`VectorStore` 类——文档入库 + 语义检索

---

## 一、概念对齐：向量数据库做什么

```
存：Document → Chunking → Embedding → 向量 + 原文 → 写入 ChromaDB
查：用户问题 → Embedding → 在 ChromaDB 里找 Top-K 最近向量 → 返回原文
```

ChromaDB 是轻量级向量库，纯 Python，零配置：
- 存：`collection.add(documents, embeddings, metadatas)`
- 查：`collection.query(query_embeddings, n_results=5)`

---

## 二、动手实战（30 分钟）

### 任务 1：创建 `vector_store.py`

在 `src/rag_system/vector_store.py`：

```python
"""向量存储——ChromaDB 封装。

教学点：
  1. ChromaDB Client：内存模式（开发）vs 持久化（生产）
  2. add：文档 + 向量 + 元数据 一起存
  3. query：给向量返回最相似的 Top-K 文档
"""

import chromadb
from rag_system.loader import Document
from rag_system.embedder import Embedder


class VectorStore:
    """ChromaDB 向量存储——存文档，检索文档。"""

    def __init__(self, embedder: Embedder, persist_dir: str | None = None):
        self.embedder = embedder
        if persist_dir:
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.Client()  # 内存模式，关了就没了

        self.collection = self.client.get_or_create_collection(
            name="rag_documents",
            metadata={"hnsw:space": "cosine"},  # 用余弦相似度
        )

    def add_documents(self, documents: list[Document]) -> None:
        """批量入库：向量化 → 存 ChromaDB。"""
        if not documents:
            return

        texts = [doc.content for doc in documents]
        embeddings = self.embedder.embed_batch(texts)
        ids = [f"doc_{self.collection.count() + i}" for i in range(len(documents))]
        metadatas = [doc.metadata for doc in documents]

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(f"  入库 {len(documents)} 条，当前总数: {self.collection.count()}")

    def query(self, query_text: str, top_k: int = 3) -> list[Document]:
        """语义检索：问题 → 向量 → Top-K 相似文档。"""
        query_embedding = self.embedder.embed(query_text)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        for i in range(len(results["ids"][0])):
            docs.append(Document(
                content=results["documents"][0][i],
                metadata={
                    **(results["metadatas"][0][i] or {}),
                    "score": 1 - results["distances"][0][i],  # distance → similarity
                },
            ))
        return docs

    def count(self) -> int:
        return self.collection.count()
```

### 任务 2：验证脚本

在 `examples/test_vector_store.py`：

```python
"""验证 ChromaDB：入库 + 检索。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.loader import DocumentLoader, Document
from rag_system.chunker import TextChunker
from rag_system.embedder import Embedder
from rag_system.vector_store import VectorStore

DATA_DIR = str(Path(__file__).parent.parent / "data")

# 1. 加载文档
loader = DocumentLoader(DATA_DIR)
documents = loader.load_all()
print(f"加载: {len(documents)} 篇文档")

# 2. 切块
chunker = TextChunker(chunk_size=200, chunk_overlap=50)
chunks = chunker.chunk(documents)
print(f"切块: {len(chunks)} 个 chunk")

# 3. 向量化 + 入库
embedder = Embedder()
store = VectorStore(embedder)
store.add_documents(chunks)

# 4. 检索
queries = [
    "什么是 RAG？",
    "人工智能是什么？",
    "机器学习如何学习？",
]

for q in queries:
    print(f"\n=== 查询: {q} ===")
    results = store.query(q, top_k=2)
    for i, doc in enumerate(results):
        score = doc.metadata.get("score", 0)
        src = doc.metadata.get("source", "?")
        print(f"  #{i+1} [{src}] (相似度: {score:.4f})")
        print(f"      {doc.content[:80]}...")
```

运行：

```bash
cd rag-system && python examples/test_vector_store.py
```

---

## 三、验收标准

- 3 个查询各自返回 Top-2 结果
- "什么是 RAG" 命中的 chunk 应该来自 `sample.md`（因为那个文件讲 RAG）
- "人工智能是什么" 命中的 chunk 应该来自 `sample.txt`（因为那个文件讲 AI）
- 相似度分数合理（相关文档 > 0.3）

---

## 四、概念速查：ChromaDB 模式

| 模式 | 代码 | 特点 |
|------|------|------|
| 内存 | `chromadb.Client()` | 关程序就没了，开发测试用 |
| 持久化 | `chromadb.PersistentClient(path="./db")` | 存磁盘，生产用 |
| 客户端/服务端 | `chromadb.HttpClient(host=..., port=...)` | 多进程共享，大规模用 |
