"""文档加载器——统一加载 PDF / Markdown / TXT。

教学点：
  1. 策略模式：根据文件扩展名自动选解析器
  2. @dataclass：统一的 Document 数据结构
  3. 错误处理：单个文件失败不影响其他文件
"""

from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Document:
    """一个文档 = 正文 + 元数据。"""
    content: str
    metadata: dict = field(default_factory=dict)

class DocumentLoader:
    """根据文件扩展名自动选择解析器，加载文档。"""

    def __init__(self,directory: str):
        self.directory = Path(directory)
    
    def _load_file(self, filepath: Path) -> list[Document]:
        """根据扩展名选择解析器"""
        suffix = filepath.suffix.lower()
        if suffix == ".pdf":
            return self._load_pdf(filepath)
        elif suffix in [".md", ".markdown"]:
            return self._load_markdown(filepath)
        elif suffix == ".txt":
            return self._load_txt(filepath)
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")

    def load_all(self) -> list[Document]:
        """加载目录下的所有文档，返回 Document 列表。"""
        if not self.directory.exists():
            raise ValueError(f"目录不存在: {self.directory}")
        
        documents = []
        for filepath in self.directory.iterdir():
            if not filepath.is_file():
                continue
            try:
                docs = self._load_file(filepath)
                documents.extend(docs)
                print(f"  [OK] {filepath.name} ({len(docs)} 页/段)")
            except Exception as e:
                print(f"  [错误] {filepath.name} 加载失败: {e}")
        return documents

    def _load_pdf(self, filepath: Path) -> list[Document]:
        """解析 PDF，每页一个Document"""
        from pypdf import PdfReader

        reader = PdfReader(str(filepath))
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                docs.append(Document(content=text, metadata={"source": filepath.name, "page": i+1, "format": "pdf"}))
        return docs
    
    def _load_markdown(self, filepath: Path) -> list[Document]:
        """解析 Markdown，整文件一个Document"""
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            return []
        return [Document(content=text, metadata={"source": filepath.name, "format": "markdown"})]
    
    def _load_txt(self, filepath: Path) -> list[Document]:
        """解析 TXT，整文件一个Document"""
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            return []
        return [Document(content=text, metadata={"source": filepath.name, "format": "txt"})]
    