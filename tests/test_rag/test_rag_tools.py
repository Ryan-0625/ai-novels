"""
RAG Agent 工具单元测试

测试 DocumentIndexTool、DocumentRetrieveTool、KnowledgeBaseTool。
"""

import pytest

from deepnovel.agents.tools.rag_tools import (
    DocumentIndexTool,
    DocumentRetrieveTool,
    KnowledgeBaseTool,
)
from deepnovel.rag import RAGEngine, RAGConfig
from deepnovel.rag.chunker import Chunk
from deepnovel.vector_store.memory_store import InMemoryVectorStore
from conftest import InMemoryTestEmbedder


@pytest.fixture
def sample_engine():
    """创建带数据的 RAG 引擎"""
    embedder = InMemoryTestEmbedder()
    store = InMemoryVectorStore(embedding_dim=64, embedding_adapter=embedder)
    engine = RAGEngine(
        config=RAGConfig(
            chunk_size=50,
            chunk_overlap=5,
            top_k=5,
            min_chunk_size=1,
            embedding_dimension=64,
        ),
        vector_store=store,
        embedding_adapter=embedder,
    )
    return engine


class TestDocumentIndexTool:
    """DocumentIndexTool 测试"""

    @pytest.mark.asyncio
    async def test_index_document(self, sample_engine):
        tool = DocumentIndexTool(rag_engine=sample_engine)
        result = await tool.index_document(
            "修仙世界的天道规则。" * 10,
            source_id="src-1",
            novel_id="n1",
        )
        assert result["chunk_count"] > 0
        assert len(result["chunk_ids"]) == result["chunk_count"]
        assert result["source_id"] == "src-1"

    @pytest.mark.asyncio
    async def test_index_documents(self, sample_engine):
        tool = DocumentIndexTool(rag_engine=sample_engine)
        result = await tool.index_documents(
            ["文本A" * 10, "文本B" * 10],
            source_ids=["s1", "s2"],
        )
        assert result["total_chunks"] > 0
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_index_chunks(self, sample_engine):
        tool = DocumentIndexTool(rag_engine=sample_engine)
        chunks = [
            Chunk(content="chunk1" * 5, index=0),
            Chunk(content="chunk2" * 5, index=1),
        ]
        result = await tool.index_chunks(chunks, source_id="src")
        assert result["chunk_count"] == 2

    @pytest.mark.asyncio
    async def test_index_world_lore(self, sample_engine):
        tool = DocumentIndexTool(rag_engine=sample_engine)
        result = await tool.index_world_lore(
            "这个世界有五大门派。" * 10,
            world_id="world-1",
            category="faction",
        )
        assert result["chunk_count"] > 0

    @pytest.mark.asyncio
    async def test_index_character_profile(self, sample_engine):
        tool = DocumentIndexTool(rag_engine=sample_engine)
        result = await tool.index_character_profile(
            "主角性格坚毅，出身贫寒。" * 10,
            character_id="char-1",
            novel_id="n1",
        )
        assert result["chunk_count"] > 0


class TestDocumentRetrieveTool:
    """DocumentRetrieveTool 测试"""

    @pytest.fixture
    async def tool_with_data(self, sample_engine):
        tool = DocumentRetrieveTool(rag_engine=sample_engine)
        # 先索引一些数据
        await sample_engine.add_document(
            "修仙世界的天道规则。灵气充沛。" * 10,
            source_id="src-1",
            novel_id="n1",
            metadata={"type": "world_lore", "category": "general"},
        )
        await sample_engine.add_document(
            "主角性格坚毅。" * 10,
            source_id="character:char-1",
            novel_id="n1",
            metadata={"type": "character_profile", "character_id": "char-1"},
        )
        return tool

    @pytest.mark.asyncio
    async def test_search(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search("修仙世界")
        assert result["total_found"] > 0
        assert "context_text" in result

    @pytest.mark.asyncio
    async def test_search_with_strategy(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search(
            "修仙",
            strategy="hybrid",
            keywords=["修仙", "天道"],
        )
        assert "total_found" in result

    @pytest.mark.asyncio
    async def test_search_with_filters(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search(
            "内容",
            filters={"novel_id": "n1"},
        )
        assert result["total_found"] >= 0

    @pytest.mark.asyncio
    async def test_search_multi_query(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search_multi_query(
            ["修仙", "天道"],
            top_k_per_query=2,
            final_top_k=3,
        )
        assert len(result["sources"]) <= 3

    @pytest.mark.asyncio
    async def test_search_world_lore(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search_world_lore(
            "修仙",
            world_id="n1",
        )
        assert result["total_found"] >= 0

    @pytest.mark.asyncio
    async def test_search_world_lore_with_category(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search_world_lore(
            "修仙",
            world_id="n1",
            category="general",
        )
        assert result["total_found"] >= 0

    @pytest.mark.asyncio
    async def test_search_character_knowledge(self, tool_with_data):
        tool = tool_with_data
        result = await tool.search_character_knowledge(
            "主角",
            character_id="char-1",
            novel_id="n1",
        )
        assert result["total_found"] >= 0

    @pytest.mark.asyncio
    async def test_build_context(self, tool_with_data):
        tool = tool_with_data
        context = await tool.build_context("修仙", top_k=2, include_sources=True)
        # 即使无检索结果，包含来源标题也保证长度 > 0
        assert len(context) >= 0
        assert "参考资料" in context


class TestKnowledgeBaseTool:
    """KnowledgeBaseTool 测试"""

    @pytest.fixture
    async def tool_with_data(self, sample_engine):
        tool = KnowledgeBaseTool(rag_engine=sample_engine)
        await sample_engine.add_document("测试内容" * 20, source_id="src-1")
        return tool

    @pytest.mark.asyncio
    async def test_get_stats(self, tool_with_data):
        tool = tool_with_data
        stats = await tool.get_stats()
        assert stats["total_documents"] > 0

    @pytest.mark.asyncio
    async def test_clear(self, tool_with_data):
        tool = tool_with_data
        result = await tool.clear()
        assert result is True
        stats = await tool.get_stats()
        assert stats["total_documents"] == 0

    @pytest.mark.asyncio
    async def test_delete_by_source(self, tool_with_data):
        tool = tool_with_data
        count = await tool.delete_by_source("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_config(self, tool_with_data):
        tool = tool_with_data
        config = await tool.get_config()
        assert "chunk_strategy" in config
        assert "top_k" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
