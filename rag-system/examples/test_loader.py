"""验证文档加载器。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.loader import DocumentLoader

DATA_DIR = str(Path(__file__).parent.parent / "data")

loader = DocumentLoader(DATA_DIR)
documents = loader.load_all()

print(f"\n共加载 {len(documents)} 个文档\n")
for doc in documents:
    src = doc.metadata.get("source", "?")
    page = doc.metadata.get("page", "")
    preview = doc.content[:80].replace("\n", " ")
    page_info = f" 第{page}页" if page else ""
    print(f"[{src}{page_info}] {preview}...")