"""
RAG 引擎 — 文档检索增强生成集成层

整合分块、索引、检索三大组件，提供统一的文档知识库接口。
支持多种检索策略和自动文档管理。

@file: rag/rag_engine.py
@date: 2026-04-29
"""

import os
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from deepnovel.llm.embedding_adapter import EmbeddingAdapter, EmbeddingConfig, EmbeddingProvider
from deepnovel.rag.chunker import Chunk, ChunkStrategy, TextChunker
from deepnovel.rag.indexer import DocumentIndexer
from deepnovel.rag.retriever import RetrievedChunk, SemanticRetriever
from deepnovel.vector_store import VectorStore
from deepnovel.vector_store.memory_store import InMemoryVectorStore


def _get_default_embedding_config() -> tuple[str, str]:
    """获取默认 embedding 配置（优先 Ollama，可环境变量覆盖）"""
    provider = os.environ.get("EMBEDDING_PROVIDER", "ollama").lower()
    model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
    return provider, model


@dataclass
class RAGConfig:
    """RAG 引擎配置"""

    chunk_strategy: ChunkStrategy = ChunkStrategy.SEMANTIC
    chunk_size: int = 500
    chunk_overlap: int = 50
    min_chunk_size: int = 50
    top_k: int = 5
    min_score: float = 0.0
    keyword_weight: float = 0.3
    diversity_lambda: float = 0.5
    embedding_dimension: int = 768
    embedding_provider: str = field(default_factory=lambda: _get_default_embedding_config()[0])
    embedding_model: str = field(default_factory=lambda: _get_default_embedding_config()[1])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_strategy": self.chunk_strategy.value,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "min_chunk_size": self.min_chunk_size,
            "top_k": self.top_k,
            "min_score": self.min_score,
            "keyword_weight": self.keyword_weight,
            "diversity_lambda": self.diversity_lambda,
            "embedding_dimension": self.embedding_dimension,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
        }


@dataclass
class RAGResult:
    """RAG 检索结果"""

    query: str
    chunks: List[RetrievedChunk] = field(default_factory=list)
    strategy: str = "vector"
    total_found: int = 0

    @property
    def context_text(self) -> str:
        """将所有 chunk 拼接为上下文文本"""
        return "\n\n---\n\n".join(
            f"[{i + 1}] {c.content}"
            for i, c in enumerate(self.chunks)
        )

    @property
    def sources(self) -> List[Dict[str, Any]]:
        """来源信息列表"""
        return [
            {
                "id": c.id,
                "score": round(c.final_score, 4),
                "metadata": c.metadata,
            }
            for c in self.chunks
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "strategy": self.strategy,
            "total_found": self.total_found,
            "context_text": self.context_text,
            "sources": self.sources,
        }


class RAGEngine:
    """RAG 引擎

    提供完整的文档知识库生命周期管理：
    1. 文档分块 (chunker)
    2. 向量索引 (indexer)
    3. 语义检索 (retriever)
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        vector_store: Optional[VectorStore] = None,
        embedding_adapter: Optional[EmbeddingAdapter] = None,
        chunker: Optional[TextChunker] = None,
    ):
        self.config = config or RAGConfig()
        self._store = vector_store or InMemoryVectorStore()

        # 初始化 embedding adapter（优先真实模型，失败回退 mock）
        if embedding_adapter:
            self._embedder = embedding_adapter
        else:
            try:
                self._embedder = EmbeddingAdapter(
                    EmbeddingConfig(
                        provider=self.config.embedding_provider,
                        model=self.config.embedding_model,
                        dimension=self.config.embedding_dimension,
                    )
                )
                # 健康检查验证可用性
                health = self._embedder.health_check()
                if health.get("status") != "healthy":
                    raise RuntimeError(f"Embedding backend unhealthy: {health}")
            except Exception as e:
                warnings.warn(
                    f"Embedding backend '{self.config.embedding_provider}' failed ({e}), "
                    f"falling back to mock embeddings. "
                    f"Set EMBEDDING_PROVIDER env var to configure.",
                    RuntimeWarning,
                )
                self._embedder = EmbeddingAdapter(
                    EmbeddingConfig(
                        provider="mock",
                        model="mock-model",
                        dimension=self.config.embedding_dimension,
                    )
                )

        # 初始化分块器
        if chunker:
            self._chunker = chunker
        else:
            self._chunker = TextChunker(
                strategy=self.config.chunk_strategy,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                min_chunk_size=self.config.min_chunk_size,
            )

        # 初始化索引器和检索器
        self._indexer = DocumentIndexer(
            vector_store=self._store,
            embedding_adapter=self._embedder,
        )
        self._retriever = SemanticRetriever(
            vector_store=self._store,
            embedding_adapter=self._embedder,
            top_k=self.config.top_k,
        )

    @property
    def indexer(self) -> DocumentIndexer:
        return self._indexer

    @property
    def retriever(self) -> SemanticRetriever:
        return self._retriever

    @property
    def chunker(self) -> TextChunker:
        return self._chunker

    # ---- 文档管理 ----

    async def add_document(
        self,
        text: str,
        *,
        source_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """添加文档到知识库

        自动分块并索引。

        Returns:
            文档块 ID 列表
        """
        chunks = self._chunker.chunk(
            text,
            source_id=source_id,
            novel_id=novel_id,
            **(metadata or {}),
        )
        return await self._indexer.index_chunks(
            chunks,
            source_id=source_id,
            novel_id=novel_id,
        )

    async def add_documents(
        self,
        texts: List[str],
        *,
        source_ids: Optional[List[str]] = None,
        novel_id: Optional[str] = None,
    ) -> List[List[str]]:
        """批量添加文档

        Returns:
            每篇文档的块 ID 列表
        """
        source_ids = source_ids or [None] * len(texts)
        results = []
        for text, sid in zip(texts, source_ids):
            ids = await self.add_document(
                text,
                source_id=sid,
                novel_id=novel_id,
            )
            results.append(ids)
        return results

    async def add_chunks(
        self,
        chunks: List[Chunk],
        *,
        source_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> List[str]:
        """直接添加预分块文档

        Returns:
            文档块 ID 列表
        """
        return await self._indexer.index_chunks(
            chunks,
            source_id=source_id,
            novel_id=novel_id,
        )

    # ---- 检索 ----

    async def query(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: Optional[float] = None,
        strategy: str = "vector",
        keywords: Optional[List[str]] = None,
    ) -> RAGResult:
        """查询知识库

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 元数据过滤条件
            min_score: 最低相似度分数
            strategy: 检索策略
                - "vector": 纯向量检索
                - "hybrid": 向量 + 关键词混合检索
                - "diverse": MMR 多样性检索
            keywords: 混合检索时的关键词列表

        Returns:
            RAGResult 检索结果
        """
        k = top_k or self.config.top_k
        score_threshold = min_score if min_score is not None else self.config.min_score

        if strategy == "hybrid" and keywords:
            chunks = await self._retriever.retrieve_with_keywords(
                query,
                keywords=keywords,
                top_k=k,
                keyword_weight=self.config.keyword_weight,
            )
        elif strategy == "diverse":
            chunks = await self._retriever.retrieve_diverse(
                query,
                top_k=k,
                diversity_lambda=self.config.diversity_lambda,
            )
        else:
            chunks = await self._retriever.retrieve(
                query,
                top_k=k,
                filters=filters,
                min_score=score_threshold,
            )

        # 过滤低分结果（hybrid/diverse 策略后）
        if strategy != "vector":
            chunks = [c for c in chunks if c.final_score >= score_threshold]

        return RAGResult(
            query=query,
            chunks=chunks,
            strategy=strategy,
            total_found=len(chunks),
        )

    async def query_multi(
        self,
        queries: List[str],
        *,
        top_k_per_query: int = 3,
        final_top_k: Optional[int] = None,
        strategy: str = "vector",
    ) -> RAGResult:
        """多查询检索

        融合多个相关查询的结果，适合复杂问题分解。

        Args:
            queries: 多个查询文本
            top_k_per_query: 每个查询的返回数
            final_top_k: 最终返回数
            strategy: 检索策略

        Returns:
            RAGResult 检索结果
        """
        chunks = await self._retriever.retrieve_multi_query(
            queries,
            top_k_per_query=top_k_per_query,
            final_top_k=final_top_k or self.config.top_k,
        )

        return RAGResult(
            query=" | ".join(queries),
            chunks=chunks,
            strategy=f"multi_query_{strategy}",
            total_found=len(chunks),
        )

    # ---- 管理 ----

    async def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        index_stats = await self._indexer.get_stats()
        return {
            **index_stats,
            "chunk_strategy": self.config.chunk_strategy.value,
            "chunk_size": self.config.chunk_size,
            "retriever_top_k": self.config.top_k,
        }

    async def clear(self) -> bool:
        """清空知识库"""
        return await self._store.clear()

    async def delete_by_source(self, source_id: str) -> int:
        """按来源删除文档"""
        return await self._indexer.delete_by_source(source_id)

    # ---- 上下文构建 ----

    def build_prompt_context(
        self,
        result: RAGResult,
        *,
        max_tokens: Optional[int] = None,
        include_sources: bool = True,
    ) -> str:
        """构建 LLM Prompt 上下文

        将检索结果格式化为适合插入 Prompt 的文本。

        Args:
            result: RAG 检索结果
            max_tokens: 最大 token 数（粗略按字符数估算）
            include_sources: 是否包含来源标注

        Returns:
            格式化上下文文本
        """
        parts = []

        if include_sources:
            parts.append("## 参考资料\n")

        context = result.context_text

        # 粗略截断（假设 1 token ≈ 1.5 中文字符 或 4 英文字符）
        if max_tokens:
            max_chars = max_tokens * 3  # 保守估算
            if len(context) > max_chars:
                context = context[:max_chars] + "\n...（内容已截断）"

        parts.append(context)

        if include_sources and result.sources:
            parts.append("\n## 来源\n")
            for src in result.sources:
                meta = src.get("metadata", {})
                source_name = meta.get("source_id", "未知")
                parts.append(f"- {source_name} (相关度: {src['score']})")

        return "\n".join(parts)
