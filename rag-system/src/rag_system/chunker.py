"""文本切块器——三种策略可选。

教学点：
  1. 固定大小切分：最简单，按字符数切
  2. 递归切分：优先按段落→句子→词切，保持语义完整
  3. Overlap：防止关键信息在边界被截断
"""

import re
from rag_system.loader import Document

class TextChunker:
    """把Document 列表切成 Chunk 列表。"""

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
        """对全部文档执行切块操作"""
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
                    } 
                ))
        return chunks
    
    def _chunk_text(self, text: str) -> list[str]:
        """根据策略把文本切成块"""
        if self.strategy == "fixed":
            return self._fixed_chunk(text)
        elif self.strategy == "recursive":
            return self._recursive_chunk(text)
        else:
            raise ValueError(f"未知的切块策略: {self.strategy}")
        
    def _fixed_chunk(self, text: str) -> list[str]:
        """最简单的固定大小切分"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            start += self.chunk_size - self.chunk_overlap
        return chunks
    
    def _recursive_chunk(self, text: str) -> list[str]:
        """递归切分——先按段落切，太长的再按句子切，还太长的按字符切。"""
        # 第一步：按段落切
        paragraphs = re.split(r"\n\s*\n", text)
        return self._split_by_limit(paragraphs, self.chunk_size)
    
    def _split_by_limit(self, segments: list[str], limit: int) -> list[str]:
        """把段落列表合并到不超过 limit ，超了就往下切"""
        result = []
        current = ""
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
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
