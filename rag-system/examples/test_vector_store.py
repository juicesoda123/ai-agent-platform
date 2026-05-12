"""验证 ChromaDB：入库 + 检索。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.loader import DocumentLoader
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
]

for q in queries:
    print(f"\n=== 查询: {q} ===")
    results = store.query(q, top_k=2)
    for i, doc in enumerate(results):
        score = doc.metadata.get("score", 0)
        src = doc.metadata.get("source", "?")
        print(f"  #{i+1} [{src}] (相似度: {score:.4f})")
        print(f"      {doc.content[:80]}...")
