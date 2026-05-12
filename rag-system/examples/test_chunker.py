"""对比三种 Chunking 策略。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.loader import DocumentLoader
from rag_system.chunker import TextChunker

DATA_DIR = str(Path(__file__).parent.parent / "data")

loader = DocumentLoader(DATA_DIR)
documents = loader.load_all()
print(f"原始文档: {len(documents)} 个\n")

for strategy in ("fixed", "recursive"):
    chunker = TextChunker(chunk_size=200, chunk_overlap=40, strategy=strategy)
    chunks = chunker.chunk(documents)

    print(f"=== {strategy} 策略 ===")
    print(f"切块数: {len(chunks)}")
    for c in chunks[:3]:  # 只看前 3 块
        print(f"  [{c.metadata['source']} chunk{c.metadata['chunk_index']}] "
              f"({len(c.content)} 字): {c.content[:60]}...")
    print()