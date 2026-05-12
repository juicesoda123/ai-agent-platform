"""向量存储——纯 numpy 实现，不依赖 ChromaDB。

教学点：
  1. 向量检索原理：存向量 → 算余弦相似度 → 取 Top-K
  2. 和 ChromaDB 一样的 API，底层自己写
"""

import numpy as np
from rag_system.loader import Document
from rag_system.embedder import Embedder


class VectorStore:
    """内存向量存储——学习用。生产环境换 ChromaDB/Milvus。"""

    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self._documents: list[Document] = []
        self._embeddings: np.ndarray | None = None

    def add_documents(self, documents: list[Document]) -> None:
        if not documents:
            return
        vectors = self.embedder.embed_batch([doc.content for doc in documents])
        new_emb = np.array(vectors)
        if self._embeddings is not None:
            self._embeddings = np.vstack([self._embeddings, new_emb])
        else:
            self._embeddings = new_emb
        self._documents.extend(documents)
        print(f"  入库 {len(documents)} 条，当前总数: {self.count()}")

    def query(self, query_text: str, top_k: int = 3) -> list[Document]:
        if self._embeddings is None:
            return []

        query_vec = np.array(self.embedder.embed(query_text))
        # 余弦相似度 = 点积 / (norm * norm)
        dot = np.dot(self._embeddings, query_vec)
        norms = np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(query_vec)
        scores = dot / (norms + 1e-10)

        top_indices = np.argsort(scores)[-top_k:][::-1]  # 降序取 Top-K

        results = []
        for idx in top_indices:
            doc = self._documents[idx]
            results.append(Document(
                content=doc.content,
                metadata={**doc.metadata, "score": float(scores[idx])},
            ))
        return results

    def count(self) -> int:
        return len(self._documents)
