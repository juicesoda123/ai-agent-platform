"""Embedding 服务——文本 → 向量，用本地模型，不依赖外部 API。

教学点：
  1. sentence-transformers：一行代码加载模型
  2. 批量向量化 + 余弦相似度
"""

import os
import numpy as np
from sentence_transformers import SentenceTransformer

# 国内用 hf-mirror.com 镜像下载模型
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


class Embedder:
    """本地 Embedding 模型——不花钱，离线可用。"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name, local_files_only=True)

    def embed(self, text: str) -> list[float]:
        """单条文本 → 向量。"""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。"""
        embeddings = self.model.encode(texts)
        return [emb.tolist() for emb in embeddings]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """余弦相似度——1.0 = 完全相同，0 = 不相关。"""
        va = np.array(a)
        vb = np.array(b)
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))
