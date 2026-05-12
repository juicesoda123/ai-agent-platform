"""验证 Embedding + 余弦相似度。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.embedder import Embedder


def main() -> None:
    embedder = Embedder()  # 本地模型，不需要 API Key

    texts = [
        "今天天气真好",
        "今天天气不错",
        "Python 是一门编程语言",
        "机器学习是 AI 的一个分支",
    ]

    vectors = embedder.embed_batch(texts)
    print(f"{len(vectors)} 条文本全部向量化，维度: {len(vectors[0])}\n")

    # 相似度矩阵
    print("余弦相似度：")
    for i, a in enumerate(texts):
        for j, b in enumerate(texts):
            if j > i:
                sim = Embedder.cosine_similarity(vectors[i], vectors[j])
                print(f"  [{a}] vs [{b}]: {sim:.4f}")

    sim_same = Embedder.cosine_similarity(vectors[0], vectors[1])
    sim_diff = Embedder.cosine_similarity(vectors[0], vectors[2])
    print(f"\n'天气真好' vs '天气不错': {sim_same:.4f} (期望 > 0.5)")
    print(f"'天气真好' vs 'Python':     {sim_diff:.4f} (期望 < 0.3)")


if __name__ == "__main__":
    main()
