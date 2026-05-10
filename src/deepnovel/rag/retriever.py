"""
语义检索器 — 多策略检索与重排序

支持:
- 纯向量检索
- 混合检索（向量 + 关键词）
- 重排序（MMR 多样性 + 相关性）
- 过滤检索

@file: rag/retriever.py
@date: 2026-04-29
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from deepnovel.llm.embedding_adapter import EmbeddingAdapter
from deepnovel.vector_store import SearchResult, VectorStore
from deepnovel.vector_store.memory_store import InMemoryVectorStore


@dataclass
class RetrievedChunk:
    """检索到的文档块"""

    id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    rerank_score: Optional[float] = None

    @property
    def final_score(self) -> float:
        """最终得分（如有重排序则使用重排序分数）"""
        return self.rerank_score if self.rerank_score is not None else self.score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "score": round(self.score, 4),
            "rerank_score": round(self.rerank_score, 4) if self.rerank_score is not None else None,
            "metadata": self.metadata,
        }


class SemanticRetriever:
    """语义检索器"""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_adapter: Optional[EmbeddingAdapter] = None,
        top_k: int = 5,
    ):
        self._store = vector_store or InMemoryVectorStore()
        self._embedder = embedding_adapter
        self.top_k = top_k

    async def retrieve(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> List[RetrievedChunk]:
        """向量检索"""
        k = top_k or self.top_k
        results = await self._store.search(query, top_k=k * 2, filters=filters)

        chunks = [
            RetrievedChunk(
                id=r.id,
                content=r.content,
                score=r.score,
                metadata=r.metadata or {},
            )
            for r in results
            if r.score >= min_score
        ]

        return chunks[:k]

    async def retrieve_with_keywords(
        self,
        query: str,
        *,
        keywords: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        keyword_weight: float = 0.3,
    ) -> List[RetrievedChunk]:
        """混合检索：向量 + 关键词"""
        k = top_k or self.top_k

        # 向量检索（放宽到更多结果）
        vector_results = await self.retrieve(query, top_k=k * 3)

        if not keywords:
            return vector_results[:k]

        # 关键词匹配
        keyword_results = self._keyword_search(query, keywords, vector_results)

        # 混合评分
        combined = self._merge_scores(vector_results, keyword_results, keyword_weight)
        combined.sort(key=lambda x: x.final_score, reverse=True)

        return combined[:k]

    def _keyword_search(
        self,
        query: str,
        keywords: List[str],
        candidates: List[RetrievedChunk],
    ) -> Dict[str, float]:
        """关键词匹配评分"""
        query_terms = set(query.lower().split()) | set(k.lower() for k in keywords)
        scores = {}

        for chunk in candidates:
            content_lower = chunk.content.lower()
            matches = sum(1 for term in query_terms if term in content_lower)
            scores[chunk.id] = min(1.0, matches / max(len(query_terms), 1))

        return scores

    def _merge_scores(
        self,
        vector_results: List[RetrievedChunk],
        keyword_scores: Dict[str, float],
        keyword_weight: float,
    ) -> List[RetrievedChunk]:
        """合并向量分数和关键词分数"""
        merged = []
        seen = set()

        for chunk in vector_results:
            kw_score = keyword_scores.get(chunk.id, 0.0)
            combined = chunk.score * (1 - keyword_weight) + kw_score * keyword_weight
            chunk.rerank_score = round(combined, 4)
            merged.append(chunk)
            seen.add(chunk.id)

        return merged

    async def retrieve_diverse(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        diversity_lambda: float = 0.5,
    ) -> List[RetrievedChunk]:
        """MMR 多样性检索

        Args:
            diversity_lambda: 平衡相关性和多样性的参数
                0 = 最大多样性，1 = 最大相关性
        """
        k = top_k or self.top_k

        # 初始检索更多结果
        candidates = await self.retrieve(query, top_k=k * 4)
        if len(candidates) <= k:
            return candidates

        # MMR 选择
        selected: List[RetrievedChunk] = []
        remaining = list(candidates)

        while len(selected) < k and remaining:
            best_mmr_score = -1.0
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                # 相关性部分
                relevance = candidate.score

                # 多样性部分：与已选结果的最大相似度
                max_sim = 0.0
                if selected and self._embedder:
                    candidate_emb = self._embedder.embed(candidate.content)
                    for s in selected:
                        s_emb = self._embedder.embed(s.content)
                        sim = EmbeddingAdapter.cosine_similarity(candidate_emb, s_emb)
                        max_sim = max(max_sim, sim)

                mmr_score = diversity_lambda * relevance - (1 - diversity_lambda) * max_sim

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            selected.append(remaining.pop(best_idx))

        return selected

    async def retrieve_multi_query(
        self,
        queries: List[str],
        *,
        top_k_per_query: int = 3,
        final_top_k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """多查询检索（融合多个相关查询的结果）"""
        all_results: Dict[str, RetrievedChunk] = {}

        for query in queries:
            results = await self.retrieve(query, top_k=top_k_per_query)
            for r in results:
                if r.id not in all_results:
                    all_results[r.id] = r
                else:
                    # 提升分数
                    all_results[r.id].score = max(all_results[r.id].score, r.score)

        sorted_results = sorted(all_results.values(), key=lambda x: x.score, reverse=True)
        final_k = final_top_k or self.top_k
        return sorted_results[:final_k]
