"""
内存向量存储实现

用于测试和本地开发，无需外部依赖。
使用简单的余弦相似度计算。

@file: vector_store/memory_store.py
@date: 2026-04-29
"""

import math
from typing import Any, Dict, List, Optional

from .enhanced_base import SearchResult, VectorDocument, VectorStore


def _simple_hash_embedding(text: str, dim: int = 128) -> List[float]:
    """简单的确定性哈希嵌入（用于测试）

    生成固定维度的向量，相同文本总是产生相同嵌入。
    不用于生产环境，仅用于测试相似度逻辑。
    """
    # 使用字符哈希生成伪随机但确定的向量
    vec = [0.0] * dim
    for i, ch in enumerate(text):
        idx = i % dim
        vec[idx] += ord(ch) / 1000.0

    # 归一化
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore(VectorStore):
    """内存向量存储

    使用 Python 字典存储文档，支持基本相似度搜索。
    适合单元测试和小规模开发场景。
    """

    def __init__(
        self,
        collection_name: str = "default",
        embedding_dim: int = 128,
        embedding_adapter=None,
    ):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self._embedder = embedding_adapter
        self._docs: Dict[str, VectorDocument] = {}
        self._connected = False

    async def connect(self) -> bool:
        """建立连接（无实际操作）"""
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        """断开连接（无实际操作）"""
        self._connected = False
        return True

    async def health_check(self) -> bool:
        """健康检查"""
        return self._connected

    async def upsert(
        self,
        documents: List[VectorDocument],
        *,
        batch_size: int = 100,
    ) -> int:
        """批量插入或更新文档"""
        count = 0
        for doc in documents:
            if doc.embedding is None:
                if self._embedder is not None:
                    doc.embedding = self._embedder.embed(doc.content)
                else:
                    doc.embedding = _simple_hash_embedding(doc.content, self.embedding_dim)
            self._docs[doc.id] = doc
            count += 1
            if count >= batch_size:
                break
        return count

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """语义搜索"""
        if self._embedder is not None:
            query_emb = self._embedder.embed(query)
        else:
            query_emb = _simple_hash_embedding(query, self.embedding_dim)

        results = []
        for doc in self._docs.values():
            # 应用过滤条件
            if filters and not self._match_filters(doc.metadata or {}, filters):
                continue

            emb = doc.embedding or _simple_hash_embedding(doc.content, self.embedding_dim)
            score = _cosine_similarity(query_emb, emb)
            results.append(
                SearchResult(
                    id=doc.id,
                    content=doc.content,
                    score=score,
                    metadata=doc.metadata or {},
                )
            )

        # 按相似度排序并截取 top_k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def delete(
        self,
        ids: List[str],
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """删除文档"""
        count = 0
        for doc_id in ids:
            if doc_id in self._docs:
                if filters and not self._match_filters(
                    self._docs[doc_id].metadata or {}, filters
                ):
                    continue
                del self._docs[doc_id]
                count += 1
        return count

    async def get(self, ids: List[str]) -> List[VectorDocument]:
        """根据ID获取文档"""
        return [self._docs[i] for i in ids if i in self._docs]

    async def count(self, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """获取文档数量"""
        if not filters:
            return len(self._docs)
        return sum(
            1
            for doc in self._docs.values()
            if self._match_filters(doc.metadata or {}, filters)
        )

    async def clear(self) -> bool:
        """清空集合"""
        self._docs.clear()
        return True

    def _match_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """检查元数据是否匹配过滤条件"""
        for key, expected in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != expected:
                return False
        return True
