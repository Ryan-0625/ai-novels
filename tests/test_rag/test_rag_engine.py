"""
RAG 引擎单元测试

测试 RAGEngine 的完整流水线：添加文档、检索、上下文构建。
"""

import pytest

from deepnovel.rag import RAGConfig, RAGResult, RAGEngine
from deepnovel.rag.chunker import Chunk, ChunkStrategy
from deepnovel.vector_store.memory_store import InMemoryVectorStore
from conftest import InMemoryTestEmbedder


class TestRAGConfig:
    """RAGConfig 测试"""

    def test_default_values(self):
        config = RAGConfig()
        assert config.chunk_strategy == ChunkStrategy.SEMANTIC
        assert config.chunk_size == 500
        assert config.top_k == 5
        assert config.min_score == 0.0

    def test_to_dict(self):
        config = RAGConfig()
        d = config.to_dict()
        assert d["chunk_strategy"] == "semantic"
        assert d["top_k"] == 5


class TestRAGResult:
    """RAGResult 测试"""

    def test_empty_result(self):
        result = RAGResult(query="test")
        assert result.total_found == 0
        assert result.context_text == ""

    def test_context_text(self):
        from deepnovel.rag.retriever import RetrievedChunk

        result = RAGResult(
            query="test",
            chunks=[
                RetrievedChunk(id="1", content="内容A", score=0.9, metadata={}),
                RetrievedChunk(id="2", content="内容B", score=0.8, metadata={}),
            ],
            total_found=2,
        )
        context = result.context_text
        assert "[1] 内容A" in context
        assert "[2] 内容B" in context

    def test_sources(self):
        from deepnovel.rag.retriever import RetrievedChunk

        result = RAGResult(
            query="test",
            chunks=[
                RetrievedChunk(id="1", content="A", score=0.9, metadata={"src": "s1"}),
            ],
        )
        assert len(result.sources) == 1
        assert result.sources[0]["id"] == "1"

    def test_to_dict(self):
        result = RAGResult(query="test", strategy="vector", total_found=0)
        d = result.to_dict()
        assert d["query"] == "test"
        assert d["strategy"] == "vector"


class TestRAGEngine:
    """RAGEngine 测试"""

    @pytest.fixture
    def engine(self):
        embedder = InMemoryTestEmbedder()
        store = InMemoryVectorStore(embedding_dim=64, embedding_adapter=embedder)
        return RAGEngine(
            config=RAGConfig(
                chunk_size=50,
                chunk_overlap=5,
                top_k=3,
                min_chunk_size=1,
                embedding_dimension=64,
                embedding_provider=embedder.config.provider,
            ),
            vector_store=store,
            embedding_adapter=embedder,
        )

    @pytest.mark.asyncio
    async def test_add_document(self, engine):
        """添加文档"""
        text = "修仙世界的天道规则很复杂。灵气充沛。" * 5
        ids = await engine.add_document(text, source_id="src-1")
        assert len(ids) > 0

    @pytest.mark.asyncio
    async def test_add_document_with_metadata(self, engine):
        """添加文档带元数据"""
        ids = await engine.add_document(
            "测试内容" * 20,
            source_id="src-1",
            novel_id="n1",
            metadata={"key": "val"},
        )
        assert len(ids) > 0

    @pytest.mark.asyncio
    async def test_add_documents(self, engine):
        """批量添加文档"""
        texts = ["文本A" * 10, "文本B" * 10]
        results = await engine.add_documents(texts, source_ids=["s1", "s2"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_add_chunks(self, engine):
        """直接添加 chunks"""
        chunks = [
            Chunk(content="chunk1" * 5, index=0),
            Chunk(content="chunk2" * 5, index=1),
        ]
        ids = await engine.add_chunks(chunks, source_id="src")
        assert len(ids) == 2

    @pytest.mark.asyncio
    async def test_query_vector(self, engine):
        """向量检索"""
        await engine.add_document(
            "修仙世界的天道规则。灵气充沛。" * 10,
            source_id="src-1",
        )
        result = await engine.query("修仙世界")
        assert result.total_found > 0
        assert result.strategy == "vector"
        assert len(result.chunks) > 0

    @pytest.mark.asyncio
    async def test_query_with_filters(self, engine):
        """过滤检索"""
        await engine.add_document(
            "修仙内容" * 10,
            source_id="src-1",
            novel_id="n1",
        )
        result = await engine.query(
            "修仙",
            filters={"novel_id": "n1"},
        )
        assert result.total_found > 0

    @pytest.mark.asyncio
    async def test_query_hybrid(self, engine):
        """混合检索"""
        await engine.add_document(
            "修仙世界的天道规则" * 10,
            source_id="src-1",
        )
        result = await engine.query(
            "修仙世界",
            strategy="hybrid",
            keywords=["修仙", "天道"],
        )
        # Mock embedding 不保证语义相关性，仅验证调用链路正常
        assert result.strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_query_diverse(self, engine):
        """多样性检索"""
        await engine.add_document(
            "修仙内容A。修仙内容B。魔法内容C。" * 10,
            source_id="src-1",
        )
        result = await engine.query(
            "修仙",
            strategy="diverse",
            top_k=2,
        )
        assert len(result.chunks) <= 2

    @pytest.mark.asyncio
    async def test_query_min_score(self, engine):
        """最低分数过滤"""
        await engine.add_document("完全不相关的内容xyz" * 5, source_id="src")
        result = await engine.query(
            "修仙世界",
            min_score=0.99,
        )
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_query_multi(self, engine):
        """多查询检索"""
        await engine.add_document(
            "修仙世界的天道规则。魔法体系的元素分类。" * 10,
            source_id="src-1",
        )
        result = await engine.query_multi(
            ["修仙", "魔法"],
            top_k_per_query=2,
            final_top_k=3,
        )
        assert len(result.chunks) <= 3

    @pytest.mark.asyncio
    async def test_get_stats(self, engine):
        """统计信息"""
        await engine.add_document("测试内容" * 20, source_id="src")
        stats = await engine.get_stats()
        assert stats["total_documents"] > 0
        assert stats["embedding_dimension"] == 64

    @pytest.mark.asyncio
    async def test_clear(self, engine):
        """清空知识库"""
        await engine.add_document("测试" * 20, source_id="src")
        assert await engine.clear() is True
        stats = await engine.get_stats()
        assert stats["total_documents"] == 0

    @pytest.mark.asyncio
    async def test_delete_by_source(self, engine):
        """按来源删除"""
        count = await engine.delete_by_source("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_build_prompt_context(self, engine):
        """构建 prompt 上下文"""
        await engine.add_document("修仙世界的天道规则。" * 10, source_id="src")
        result = await engine.query("修仙")
        context = engine.build_prompt_context(result, max_tokens=100)
        assert len(context) > 0
        assert "参考资料" in context

    @pytest.mark.asyncio
    async def test_build_prompt_context_no_sources(self, engine):
        """构建 prompt 上下文（不含来源）"""
        await engine.add_document("修仙世界的天道规则。" * 10, source_id="src")
        result = await engine.query("修仙")
        context = engine.build_prompt_context(
            result,
            include_sources=False,
            max_tokens=100,
        )
        assert "来源" not in context

    @pytest.mark.asyncio
    async def test_build_prompt_context_truncate(self, engine):
        """上下文截断"""
        await engine.add_document("测试内容" * 1000, source_id="src")
        result = await engine.query("测试")
        context = engine.build_prompt_context(result, max_tokens=10)
        assert "截断" in context or len(context) < 1000

    def test_properties(self, engine):
        """属性访问"""
        assert engine.indexer is not None
        assert engine.retriever is not None
        assert engine.chunker is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
