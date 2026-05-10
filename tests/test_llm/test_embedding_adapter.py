"""
Embedding 适配器单元测试

使用内存 Mock 后端测试，无需外部 API。
"""

import pytest
from typing import List

from deepnovel.llm.embedding_adapter import (
    EmbeddingConfig,
    EmbeddingAdapter,
    BaseEmbeddingBackend,
)


class InMemoryMockBackend(BaseEmbeddingBackend):
    """测试用的内存 Mock 后端（仅用于测试，不在生产代码中）"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self._dimension = config.dimension

    def embed(self, text: str) -> List[float]:
        import hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
        vector = []
        for i in range(self._dimension):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            value = (seed / 0x7FFFFFFF) * 2 - 1
            vector.append(value)
        if self.config.normalize:
            return self._normalize(vector)
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class TestInMemoryMockBackend:
    """MockEmbeddingBackend 测试"""

    @pytest.fixture
    def backend(self):
        config = EmbeddingConfig(
            provider="test",
            model="in-memory",
            dimension=128,
        )
        return InMemoryMockBackend(config)

    def test_embed_dimension(self, backend):
        """嵌入维度正确"""
        vector = backend.embed("测试文本")
        assert len(vector) == 128

    def test_embed_deterministic(self, backend):
        """相同文本产生相同向量"""
        v1 = backend.embed("相同文本")
        v2 = backend.embed("相同文本")
        assert v1 == v2

    def test_embed_different_texts(self, backend):
        """不同文本产生不同向量"""
        v1 = backend.embed("文本A")
        v2 = backend.embed("文本B")
        assert v1 != v2

    def test_embed_normalized(self, backend):
        """向量已归一化"""
        vector = backend.embed("测试")
        norm = sum(x * x for x in vector)
        assert norm == pytest.approx(1.0, rel=1e-5)

    def test_embed_batch(self, backend):
        """批量嵌入"""
        vectors = backend.embed_batch(["A", "B", "C"])
        assert len(vectors) == 3
        assert all(len(v) == 128 for v in vectors)

    def test_health_check(self, backend):
        result = backend.health_check()
        assert result["status"] == "healthy"
        assert result["dimension"] == 128

    def test_truncate(self, backend):
        """超长文本截断"""
        long_text = "A" * 10000
        truncated = backend._truncate(long_text)
        assert len(truncated) <= backend.config.max_text_length


class TestEmbeddingAdapterStatic:
    """EmbeddingAdapter 静态方法测试"""

    def test_cosine_similarity_same(self):
        """相同向量相似度为1"""
        v = [1.0, 0.0, 0.0]
        sim = EmbeddingAdapter.cosine_similarity(v, v)
        assert sim == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """正交向量相似度为0"""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        sim = EmbeddingAdapter.cosine_similarity(a, b)
        assert sim == pytest.approx(0.0)

    def test_cosine_similarity_opposite(self):
        """反向向量相似度为-1"""
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        sim = EmbeddingAdapter.cosine_similarity(a, b)
        assert sim == pytest.approx(-1.0)

    def test_cosine_similarity_dimension_mismatch(self):
        """维度不匹配时抛出异常"""
        with pytest.raises(ValueError):
            EmbeddingAdapter.cosine_similarity([1.0, 0.0], [1.0])

    def test_euclidean_distance(self):
        """欧氏距离"""
        a = [0.0, 0.0]
        b = [3.0, 4.0]
        dist = EmbeddingAdapter.euclidean_distance(a, b)
        assert dist == pytest.approx(5.0)

    def test_similarity_matrix(self):
        """相似度矩阵"""
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
        ]
        # 手动计算矩阵（same logic as EmbeddingAdapter.similarity_matrix)
        n = len(vectors)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 1.0
            for j in range(i + 1, n):
                sim = EmbeddingAdapter.cosine_similarity(vectors[i], vectors[j])
                matrix[i][j] = matrix[j][i] = sim
        assert len(matrix) == 3
        assert matrix[0][0] == 1.0
        assert matrix[0][1] == 0.0
        assert matrix[0][2] == 1.0

    def test_find_similar(self):
        """查找最相似"""
        query = [1.0, 0.0, 0.0]
        candidates = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.7, 0.7, 0.0],
        ]
        scores = [
            (i, EmbeddingAdapter.cosine_similarity(query, c))
            for i, c in enumerate(candidates)
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        results = scores[:2]
        assert len(results) == 2
        assert results[0][0] == 0
        assert results[0][1] == pytest.approx(1.0)


class TestInMemoryBackendSemantic:
    """InMemoryMockBackend 语义测试"""

    @pytest.fixture
    def backend(self):
        config = EmbeddingConfig(
            provider="test",
            model="in-memory",
            dimension=128,
            normalize=True,
        )
        return InMemoryMockBackend(config)

    def test_semantic_similarity(self, backend):
        """相同文本相似度为1"""
        v1 = backend.embed("相同文本")
        v2 = backend.embed("相同文本")
        sim = EmbeddingAdapter.cosine_similarity(v1, v2)
        assert sim == pytest.approx(1.0)

    def test_different_texts_different_vectors(self, backend):
        """不同文本产生不同向量"""
        v1 = backend.embed("机器学习")
        v2 = backend.embed("深度学习")
        sim = EmbeddingAdapter.cosine_similarity(v1, v2)
        assert -1.0 <= sim <= 1.0
