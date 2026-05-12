# Day 16 — Embedding：把文本变成向量

> Phase 3：RAG 系统  |  预计用时：40 分钟  |  2026-05-05

---

## 今日目标

1. 理解 Embedding 的底层逻辑——"语义相近的文本，向量距离近"
2. 学会调 DeepSeek/OpenAI 的 Embedding API
3. 学会计算余弦相似度
4. 产出：`Embedder` 类 + 相似度验证

---

## 一、概念对齐：Embedding 是什么

```
文本                              向量
"今天天气真好"    ──→  [0.12, -0.34, 0.78, ..., 0.05]   ← 1536 维
"今天天气不错"    ──→  [0.13, -0.31, 0.75, ..., 0.04]   ← 距离很近！
"Python 编程"     ──→  [-0.45, 0.67, -0.12, ..., 0.88]   ← 距离很远！
```

**向量数据库的精髓**：把用户问题转向量，在向量库里找余弦相似度最近的 Top-K 文档。不是关键词匹配，是**语义匹配**。

---

## 二、动手实战（30 分钟）

### 任务 1：创建 `embedder.py`

在 `src/rag_system/embedder.py`：

```python
"""Embedding 服务——文本 → 向量。

教学点：
  1. 调 Embedding API（不是 Chat API）
  2. 批量向量化：一次调 API 处理多条
  3. 余弦相似度：测量两个向量有多"近"
"""

import numpy as np
from openai import AsyncOpenAI


class Embedder:
    """文本向量化服务。"""

    def __init__(self, client: AsyncOpenAI, model: str = "text-embedding-3-small"):
        self.client = client
        self.model = model

    async def embed(self, text: str) -> list[float]:
        """将单条文本转成向量。"""
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化——比单条调快得多。"""
        # 去掉空字符串，记录有效索引
        valid = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not valid:
            return [[] for _ in texts]

        response = await self.client.embeddings.create(
            model=self.model,
            input=[t for _, t in valid],
        )

        # 组装结果，保持和输入一样的顺序
        vectors = [[] for _ in texts]
        for (idx, _), data in zip(valid, response.data):
            vectors[idx] = data.embedding
        return vectors

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """余弦相似度——1.0 = 完全相同，0 = 不相关。"""
        va = np.array(a)
        vb = np.array(b)
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))
```

### 任务 2：验证脚本

在 `examples/test_embedder.py`：

```python
"""验证 Embedding + 余弦相似度。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.embedder import Embedder
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


async def main() -> None:
    client = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    embedder = Embedder(client)

    texts = [
        "今天天气真好",
        "今天天气不错",
        "Python 是一门编程语言",
        "机器学习是 AI 的一个分支",
    ]

    vectors = await embedder.embed_batch(texts)
    print(f"{len(vectors)} 条文本全部向量化\n")

    # 计算相似度
    print("余弦相似度矩阵：")
    for i, a in enumerate(texts):
        for j, b in enumerate(texts):
            if j > i:
                sim = Embedder.cosine_similarity(vectors[i], vectors[j])
                print(f"  [{a}] vs [{b}]: {sim:.4f}")

    # 验证：相似的应该 > 0.8，不相关的应该 < 0.5
    sim_same = Embedder.cosine_similarity(vectors[0], vectors[1])
    sim_diff = Embedder.cosine_similarity(vectors[0], vectors[2])
    print(f"\n'天气真好' vs '天气不错': {sim_same:.4f} (期望 > 0.7)")
    print(f"'天气真好' vs 'Python':     {sim_diff:.4f} (期望 < 0.5)")


if __name__ == "__main__":
    asyncio.run(main())
```

安装 numpy：

```bash
pip install numpy
```

运行：

```bash
cd rag-system && python examples/test_embedder.py
```

---

## 三、验收标准

- "天气真好" vs "天气不错" 相似度 > 0.7
- "天气真好" vs "Python" 相似度 < 0.5
- 批量向量化成功

---

## 四、概念速查：为什么不用 Chat API 做 Embedding

| | Chat API | Embedding API |
|------|---------|-------------|
| 做什么 | 生成文本 | 生成向量 |
| 返回 | `"你好！"` | `[0.12, -0.34, ...]` |
| 速度 | 慢（生成 token） | 快（固定维度输出） |
| 价格 | 按 token 计 | 极便宜 |
