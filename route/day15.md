# Day 15 — Chunking：文本切块策略

> Phase 3：RAG 系统  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解为什么需要 Chunking——LLM Context Window 装不下整本书
2. 掌握三种切块策略：固定大小 / 语义切割 / 递归切割
3. 学会 Chunk 重叠（overlap）——防止关键信息被切断
4. 产出：`TextChunker`，三种策略可切换

---

## 一、概念对齐：为什么要切块

```
原始文档（5000 字）
        ↓
    Chunking
        ↓
┌─────────┬─────────┬─────────┬─────────┐
│ Chunk 1 │ Chunk 2 │ Chunk 3 │ Chunk 4 │  ← 每个 500 字
│ 0-500   │ 400-900 │ 800-1300│ 1200-...│     有 100 字重叠
└─────────┴─────────┴─────────┴─────────┘
```

**三个关键参数**：

| 参数 | 含义 | 推荐值 |
|------|------|--------|
| chunk_size | 每块多大 | 500-1000 字符（中文） |
| chunk_overlap | 相邻块重叠多少 | chunk_size 的 10-20% |
| 策略 | 按什么规则切 | 固定大小（简单）/ 递归（通用）/ 语义（高级） |

**为什么需要 overlap**：比如关键句"今天天气很好"刚好在 chunk 1 最后和 chunk 2 开头被截断了，没有 overlap 的话两个 chunk 都不包含完整信息，检索时就丢了。

---

## 二、动手实战（30 分钟）

### 任务 1：创建 `chunker.py`

在 `src/rag_system/chunker.py`：

```python
"""文本切块器——三种策略可选。

教学点：
  1. 固定大小切分：最简单，按字符数切
  2. 递归切分：优先按段落→句子→词切，保持语义完整
  3. Overlap：防止关键信息在边界被截断
"""

import re
from rag_system.loader import Document


class TextChunker:
    """把 Document 列表切成 Chunk 列表。"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        strategy: str = "recursive",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy

    def chunk(self, documents: list[Document]) -> list[Document]:
        """对全部文档执行切块。"""
        chunks = []
        for doc in documents:
            doc_chunks = self._chunk_text(doc.content)
            for i, chunk_text in enumerate(doc_chunks):
                chunks.append(Document(
                    content=chunk_text,
                    metadata={
                        **doc.metadata,
                        "chunk_index": i,
                        "chunk_count": len(doc_chunks),
                    },
                ))
        return chunks

    def _chunk_text(self, text: str) -> list[str]:
        """根据 strategy 选切分方式。"""
        if self.strategy == "fixed":
            return self._fixed_chunk(text)
        elif self.strategy == "recursive":
            return self._recursive_chunk(text)
        else:
            raise ValueError(f"未知策略: {self.strategy}")

    def _fixed_chunk(self, text: str) -> list[str]:
        """固定大小切分——按字符数硬切。"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start = end - self.chunk_overlap  # 下一块回退 overlap 个字符
        return chunks

    def _recursive_chunk(self, text: str) -> list[str]:
        """递归切分——先按段落切，太长的再按句子切，还太长的按字符切。"""
        # 第一步：按段落切
        paragraphs = re.split(r"\n\s*\n", text)
        return self._split_by_limit(paragraphs, self.chunk_size)

    def _split_by_limit(self, segments: list[str], limit: int) -> list[str]:
        """把段落列表合并到不超过 limit，超了就往下切。"""
        result = []
        current = ""
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            # 如果当前块 + 新段落超过限制
            if len(current) + len(seg) > limit and current:
                result.append(current.strip())
                # 新段落起点回退 overlap
                overlap_start = max(0, len(current) - self.chunk_overlap)
                current = current[overlap_start:] + "\n\n" + seg
            else:
                current = seg if not current else current + "\n\n" + seg

        if current.strip():
            result.append(current.strip())
        return result
```

### 任务 2：验证脚本

在 `examples/test_chunker.py`：

```python
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
```

运行：

```bash
cd rag-system && python examples/test_chunker.py
```

---

## 三、验收标准

- 两种策略都能正常切分
- chunk 大小接近设置值（200）
- metadata 包含 chunk_index 和 chunk_count

---

## 四、概念速查

### 固定大小 vs 递归切分

| | 固定大小 | 递归切分 |
|------|---------|---------|
| 原理 | 按字符数硬切 | 段落→句子→词逐级切 |
| 优点 | 简单、可预测 | 语义完整，不截断句子 |
| 缺点 | 可能在词中间截断 | 块大小不均匀 |
| 适用 | 纯文本/代码 | 文章/文档 |

RAG 系统一般用递归切分，中文场景优先按 `\n\n`（段落）和 `。`（句子）做分隔符。
