"""
Embedding 统一适配器 — 多提供商文本嵌入

支持:
- OpenAI (text-embedding-3-small/large)
- Ollama (本地嵌入模型)
- BGE (本地 BGE 模型 via sentence-transformers)
- 统一接口: embed / embed_batch / cosine_similarity

@file: llm/embedding_adapter.py
@date: 2026-04-29
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class EmbeddingProvider(Enum):
    """Embedding 提供商"""

    OPENAI = "openai"
    OLLAMA = "ollama"
    BGE = "bge"
    QWEN = "qwen"
    MOCK = "mock"


@dataclass
class EmbeddingConfig:
    """Embedding 配置"""

    provider: str
    model: str
    dimension: int = 1536
    batch_size: int = 100
    max_text_length: int = 8192
    normalize: bool = True
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 60


class BaseEmbeddingBackend(ABC):
    """Embedding 后端基类"""

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    @property
    def provider(self) -> str:
        return self.config.provider

    @property
    def dimension(self) -> int:
        return self.config.dimension

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """单文本嵌入"""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入"""
        pass

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            result = self.embed("test")
            return {
                "status": "healthy",
                "dimension": len(result),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def _truncate(self, text: str) -> str:
        """截断超长文本"""
        if len(text) > self.config.max_text_length:
            return text[: self.config.max_text_length]
        return text

    def _normalize(self, vector: List[float]) -> List[float]:
        """L2 归一化"""
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0:
            return vector
        return [x / norm for x in vector]



class OpenAIEmbeddingBackend(BaseEmbeddingBackend):
    """OpenAI Embedding 后端"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("Please install openai: pip install openai")

    def embed(self, text: str) -> List[float]:
        response = self._client.embeddings.create(
            model=self.config.model,
            input=self._truncate(text),
        )
        vector = response.data[0].embedding
        if self.config.normalize:
            return self._normalize(vector)
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results = []
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i : i + self.config.batch_size]
            batch = [self._truncate(t) for t in batch]
            response = self._client.embeddings.create(
                model=self.config.model,
                input=batch,
            )
            vectors = [d.embedding for d in response.data]
            if self.config.normalize:
                vectors = [self._normalize(v) for v in vectors]
            results.extend(vectors)
        return results


class OllamaEmbeddingBackend(BaseEmbeddingBackend):
    """Ollama Embedding 后端"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        try:
            import ollama

            self._client = ollama
        except ImportError:
            raise ImportError("Please install ollama: pip install ollama")

    def embed(self, text: str) -> List[float]:
        response = self._client.embeddings(
            model=self.config.model,
            prompt=self._truncate(text),
        )
        vector = response["embedding"]
        if self.config.normalize:
            return self._normalize(vector)
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # Ollama 原生不支持批量，串行处理
        return [self.embed(t) for t in texts]


class BgeEmbeddingBackend(BaseEmbeddingBackend):
    """BGE 本地 Embedding 后端 (sentence-transformers)"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(config.model)
        except ImportError:
            raise ImportError(
                "Please install sentence-transformers: pip install sentence-transformers"
            )

    def embed(self, text: str) -> List[float]:
        vector = self._model.encode(self._truncate(text)).tolist()
        if self.config.normalize:
            return self._normalize(vector)
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        texts = [self._truncate(t) for t in texts]
        vectors = self._model.encode(texts).tolist()
        if self.config.normalize:
            vectors = [self._normalize(v) for v in vectors]
        return vectors


class MockEmbeddingBackend(BaseEmbeddingBackend):
    """Mock Embedding 后端 — 返回随机单位向量（开发/测试用）"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        import random as _random
        self._rng = _random.Random(42)

    def embed(self, text: str) -> List[float]:
        vec = [self._rng.gauss(0, 1) for _ in range(self.config.dimension)]
        return self._normalize(vec)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class EmbeddingAdapter:
    """Embedding 统一适配器"""

    BACKENDS = {
        EmbeddingProvider.OPENAI: OpenAIEmbeddingBackend,
        EmbeddingProvider.OLLAMA: OllamaEmbeddingBackend,
        EmbeddingProvider.BGE: BgeEmbeddingBackend,
        EmbeddingProvider.MOCK: MockEmbeddingBackend,
    }

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        provider = EmbeddingProvider(config.provider)
        backend_class = self.BACKENDS.get(provider)
        if backend_class is None:
            raise ValueError(
                f"Unsupported embedding provider: {config.provider}. "
                f"Available: {[p.value for p in self.BACKENDS]}"
            )
        self._backend = backend_class(config)

    @property
    def dimension(self) -> int:
        return self.config.dimension

    @property
    def provider(self) -> str:
        return self.config.provider

    def embed(self, text: str) -> List[float]:
        """单文本嵌入"""
        return self._backend.embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入"""
        return self._backend.embed_batch(texts)

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return self._backend.health_check()

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        if len(a) != len(b):
            raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def euclidean_distance(a: List[float], b: List[float]) -> float:
        """计算欧氏距离"""
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def similarity_matrix(
        self, vectors: List[List[float]], metric: str = "cosine"
    ) -> List[List[float]]:
        """计算相似度矩阵"""
        n = len(vectors)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            matrix[i][i] = 1.0 if metric == "cosine" else 0.0
            for j in range(i + 1, n):
                if metric == "cosine":
                    sim = self.cosine_similarity(vectors[i], vectors[j])
                else:
                    sim = -self.euclidean_distance(vectors[i], vectors[j])
                matrix[i][j] = matrix[j][i] = sim

        return matrix

    def find_similar(
        self,
        query: List[float],
        candidates: List[List[float]],
        top_k: int = 5,
    ) -> List[tuple]:
        """查找最相似的向量

        Returns:
            List[(index, similarity)] 按相似度降序
        """
        scores = [
            (i, self.cosine_similarity(query, candidate))
            for i, candidate in enumerate(candidates)
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "dimension": self.config.dimension,
            "batch_size": self.config.batch_size,
            "normalize": self.config.normalize,
        }
