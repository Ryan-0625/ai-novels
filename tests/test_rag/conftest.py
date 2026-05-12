"""
RAG 测试共享 fixture — 使用内存 Mock 嵌入器，不依赖外部服务。
"""

from typing import List

from ai_novels.llm.embedding_adapter import BaseEmbeddingBackend, EmbeddingConfig


class InMemoryTestEmbedder(BaseEmbeddingBackend):
    """测试专用的内存 Mock 嵌入器"""

    def __init__(self, config: EmbeddingConfig = None):
        if config is None:
            config = EmbeddingConfig(provider="test", model="test", dimension=64)
        super().__init__(config)

    def embed(self, text: str) -> List[float]:
        import hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [((seed >> i) & 0xFF) / 255.0 for i in range(self.config.dimension)]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]
