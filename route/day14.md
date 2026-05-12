# Day 14 — RAG 启动：文档加载与解析

> Phase 3：RAG 系统  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解 RAG 的第一步——把各种格式的文档读进来，转成纯文本
2. 学会用 `pypdf` 解析 PDF，用原生 Python 解析 Markdown/TXT
3. 搭好 `rag-system/` 项目骨架
4. 产出：`DocumentLoader` —— 支持 PDF / Markdown / TXT 的统一加载器

---

## 一、概念对齐：RAG 的文档处理流水线

```
PDF/MD/TXT → DocumentLoader → 纯文本 → Chunking → Embedding → 向量库
              ↑ 今天做这个
```

`DocumentLoader` 的职责：**不管你丢什么格式进来，它吐出统一的 `Document` 对象**。

```python
@dataclass
class Document:
    content: str        # 文档正文
    metadata: dict      # 元数据：文件名、页数、来源路径
```

---

## 二、项目骨架

在 `AI-Agent/` 下新建 `rag-system/`：

```
rag-system/
├── .env                ← 复制 llm-client/.env
├── .gitignore
├── data/               ← 放 PDF/MD/TXT 测试文件
├── src/rag_system/
│   ├── __init__.py
│   └── loader.py       ← 今天写
└── examples/
    └── test_loader.py  ← 今天写
```

---

## 三、动手实战（30 分钟）

### 任务 1：安装依赖

```bash
pip install pypdf
```

### 任务 2：创建 `DocumentLoader`

在 `src/rag_system/loader.py`：

```python
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
    """加载指定目录下的所有文档。"""

    def __init__(self, directory: str):
        self.directory = Path(directory)

    def load_all(self) -> list[Document]:
        """加载目录下所有支持的文档。"""
        if not self.directory.exists():
            raise FileNotFoundError(f"目录不存在: {self.directory}")

        documents = []
        for filepath in self.directory.iterdir():
            if not filepath.is_file():
                continue
            try:
                docs = self._load_file(filepath)
                documents.extend(docs)
                print(f"  [OK] {filepath.name} ({len(docs)} 页/段)")
            except Exception as e:
                print(f"  [SKIP] {filepath.name}: {e}")
        return documents

    def _load_file(self, filepath: Path) -> list[Document]:
        """根据扩展名选择解析器。"""
        suffix = filepath.suffix.lower()
        if suffix == ".pdf":
            return self._load_pdf(filepath)
        elif suffix in (".md", ".markdown"):
            return self._load_markdown(filepath)
        elif suffix == ".txt":
            return self._load_txt(filepath)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def _load_pdf(self, filepath: Path) -> list[Document]:
        """解析 PDF，每页一个 Document。"""
        from pypdf import PdfReader

        reader = PdfReader(str(filepath))
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                docs.append(Document(
                    content=text.strip(),
                    metadata={
                        "source": filepath.name,
                        "page": i + 1,
                        "format": "pdf",
                    },
                ))
        return docs

    def _load_markdown(self, filepath: Path) -> list[Document]:
        """解析 Markdown——整个文件作为一个 Document。"""
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            return []
        return [Document(
            content=text.strip(),
            metadata={"source": filepath.name, "format": "markdown"},
        )]

    def _load_txt(self, filepath: Path) -> list[Document]:
        """解析 TXT——同 Markdown。"""
        text = filepath.read_text(encoding="utf-8")
        if not text.strip():
            return []
        return [Document(
            content=text.strip(),
            metadata={"source": filepath.name, "format": "txt"},
        )]
```

### 任务 3：测试数据

在 `rag-system/data/` 下创建两个测试文件：

**`data/sample.txt`**：
```
人工智能（AI）是计算机科学的一个分支，旨在创建能够执行通常需要人类智能的任务的系统。
这些任务包括学习、推理、问题解决、感知和语言理解。

机器学习是 AI 的一个子集，它使系统能够从数据中学习，而无需明确编程。
深度学习是机器学习的一个子集，使用多层神经网络来模拟人脑的学习过程。
```

**`data/sample.md`**：
```markdown
# RAG 系统简介

## 什么是 RAG

RAG（检索增强生成）是一种将信息检索与文本生成结合的技术。

## RAG 的工作流程

1. 文档加载：读取各种格式的文档
2. 文本切块：将长文档切分成小块
3. 向量化：将文本块转换为向量
4. 存储：将向量存入向量数据库
5. 检索：根据用户查询检索相关文档
6. 生成：将检索结果与用户查询一起交给 LLM 生成回答
```

### 任务 4：验证脚本

在 `examples/test_loader.py`：

```python
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
```

---

## 四、验收标准

运行：

```bash
cd rag-system && python examples/test_loader.py
```

预期看到 2 个文件被加载，TXT 1 段 + MD 1 段 = 共 2 个 Document。

---

## 五、概念速查

### 为什么 PDF 每页一个 Document，MD 却整个文件一个？

PDF 是分页的，页面之间有天然边界，每页一个 Document 方便后续 Chunking。MD/TXT 是连续文本，没有固定边界，接下来靠 Chunking 策略来切分——这是 D2 的内容。

### Document 的 metadata 有什么用？

后面检索时，你可以按 metadata 过滤（"只在 PDF 里搜"、"只看第 3 页"）、展示来源引用（"该信息来自 sample.pdf 第 5 页"）。
