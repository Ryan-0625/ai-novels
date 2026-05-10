"""
语义检索器单元测试

使用 Mock Embedding 和内存向量存储测试 SemanticRetriever。
"""

import pytest

from deepnovel.rag.retriever import RetrievedChunk, SemanticRetriever
from deepnovel.vector_store import VectorDocument
from deepnovel.vector_store.memory_store import InMemoryVectorStore
from conftest import InMemoryTestEmbedder


class TestRetrievedChunk:
    """RetrievedChunk 数据类测试"""

    def test_final_score_without_rerank(self):
        chunk = RetrievedChunk(
            id="1",
            content="test",
            score=0.8,
            metadata={},
        )
        assert chunk.final_score == 0.8

    def test_final_score_with_rerank(self):
        chunk = RetrievedChunk(
            id="1",
            content="test",
            score=0.8,
            metadata={},
            rerank_score=0.9,
        )
        assert chunk.final_score == 0.9

    def test_to_dict(self):
        chunk = RetrievedChunk(
            id="1",
            content="test",
            score=0.8,
            metadata={"k": "v"},
            rerank_score=0.9,
        )
        d = chunk.to_dict()
        assert d["id"] == "1"
        assert d["score"] == 0.8
        assert d["rerank_score"] == 0.9


class TestSemanticRetriever:
    """SemanticRetriever 测试"""

    @pytest.fixture
    async def setup_store(self):
        """创建带数据的存储和检索器"""
        embedder = InMemoryTestEmbedder()
        # 将 embedder 传给 store，确保查询和文档使用相同的嵌入方法
        store = InMemoryVectorStore(embedding_dim=64, embedding_adapter=embedder)

        # 插入测试文档
        docs = [
            VectorDocument(
                id="doc-1",
                content="修仙世界的天道规则",
                embedding=embedder.embed("修仙世界的天道规则"),
                metadata={"category": "修仙", "novel_id": "n1"},
            ),
            VectorDocument(
                id="doc-2",
                content="魔法体系的元素分类",
                embedding=embedder.embed("魔法体系的元素分类"),
                metadata={"category": "魔法", "novel_id": "n1"},
            ),
            VectorDocument(
                id="doc-3",
                content="修仙者的修炼境界",
                embedding=embedder.embed("修仙者的修炼境界"),
                metadata={"category": "修仙", "novel_id": "n2"},
            ),
            VectorDocument(
                id="doc-4",
                content="剑道修炼方法",
                embedding=embedder.embed("剑道修炼方法"),
                metadata={"category": "剑道", "novel_id": "n1"},
            ),
        ]
        await store.upsert(docs)

        retriever = SemanticRetriever(
            vector_store=store,
            embedding_adapter=embedder,
            top_k=3,
        )
        return store, retriever

    @pytest.mark.asyncio
    async def test_retrieve_basic(self, setup_store):
        """基本向量检索"""
        store, retriever = setup_store
        results = await retriever.retrieve("修仙世界")
        assert len(results) > 0
        assert len(results) <= 3
        # Mock embedding 不保证语义排序，仅验证返回结果

    @pytest.mark.asyncio
    async def test_retrieve_with_top_k(self, setup_store):
        """自定义 top_k"""
        store, retriever = setup_store
        results = await retriever.retrieve("修仙", top_k=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_retrieve_with_filters(self, setup_store):
        """过滤检索"""
        store, retriever = setup_store
        results = await retriever.retrieve(
            "修炼",
            filters={"category": "剑道"},
        )
        if results:
            assert all(r.metadata.get("category") == "剑道" for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_min_score(self, setup_store):
        """最低分数过滤"""
        store, retriever = setup_store
        results = await retriever.retrieve("完全不相关的内容xyz", min_score=0.99)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_with_keywords(self, setup_store):
        """混合检索"""
        store, retriever = setup_store
        results = await retriever.retrieve_with_keywords(
            "修仙",
            keywords=["修仙", "天道"],
            top_k=3,
        )
        assert len(results) > 0
        # 混合检索应返回 rerank_score
        assert results[0].rerank_score is not None

    @pytest.mark.asyncio
    async def test_retrieve_with_keywords_no_keywords(self, setup_store):
        """无关键词时回退到向量检索"""
        store, retriever = setup_store
        results = await retriever.retrieve_with_keywords(
            "修仙",
            keywords=None,
            top_k=2,
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_retrieve_diverse(self, setup_store):
        """MMR 多样性检索"""
        store, retriever = setup_store
        results = await retriever.retrieve_diverse(
            "修炼",
            top_k=3,
            diversity_lambda=0.5,
        )
        assert len(results) > 0
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_retrieve_diverse_few_candidates(self, setup_store):
        """候选少时直接返回"""
        store, retriever = setup_store
        results = await retriever.retrieve_diverse(
            "修炼",
            top_k=10,
        )
        # 如果候选不足直接返回
        assert len(results) <= 4  # store 里只有 4 条

    @pytest.mark.asyncio
    async def test_retrieve_multi_query(self, setup_store):
        """多查询检索"""
        store, retriever = setup_store
        results = await retriever.retrieve_multi_query(
            ["修仙", "魔法"],
            top_k_per_query=2,
            final_top_k=3,
        )
        assert len(results) <= 3
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_retrieve_multi_query_dedup(self, setup_store):
        """多查询去重"""
        store, retriever = setup_store
        results = await retriever.retrieve_multi_query(
            ["修仙", "修仙世界"],  # 两个相似查询
            top_k_per_query=2,
            final_top_k=4,
        )
        # 不应有重复文档
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
