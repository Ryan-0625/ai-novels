"""
向量索引器单元测试

使用 Mock Embedding 和内存向量存储测试 DocumentIndexer。
"""

import pytest

from deepnovel.rag.chunker import Chunk
from deepnovel.rag.indexer import DocumentIndexer
from deepnovel.vector_store.memory_store import InMemoryVectorStore
from conftest import InMemoryTestEmbedder


class TestDocumentIndexer:
    """DocumentIndexer 测试"""

    @pytest.fixture
    def indexer(self):
        store = InMemoryVectorStore(embedding_dim=64)
        embedder = InMemoryTestEmbedder()
        return DocumentIndexer(vector_store=store, embedding_adapter=embedder)

    @pytest.mark.asyncio
    async def test_index_chunks_empty(self, indexer):
        """空 chunks 返回空列表"""
        result = await indexer.index_chunks([])
        assert result == []

    @pytest.mark.asyncio
    async def test_index_chunks_basic(self, indexer):
        """正常索引 chunks"""
        chunks = [
            Chunk(content="修仙世界", index=0),
            Chunk(content="魔法体系", index=1),
        ]
        ids = await indexer.index_chunks(chunks, source_id="src-1")
        assert len(ids) == 2
        assert all(isinstance(i, str) for i in ids)

    @pytest.mark.asyncio
    async def test_index_chunks_metadata(self, indexer):
        """metadata 正确保存"""
        chunks = [
            Chunk(content="测试内容", index=0, metadata={"custom": "val"}),
        ]
        ids = await indexer.index_chunks(
            chunks, source_id="src-1", novel_id="novel-1"
        )

        # 通过 store 获取验证
        docs = await indexer.vector_store.get(ids)
        assert len(docs) == 1
        assert docs[0].metadata["source_id"] == "src-1"
        assert docs[0].metadata["novel_id"] == "novel-1"
        assert docs[0].metadata["chunk_index"] == 0
        assert docs[0].metadata["custom"] == "val"

    @pytest.mark.asyncio
    async def test_index_text(self, indexer):
        """索引原始文本（自动分块）"""
        text = "修仙世界很大。灵气充沛。" * 20
        ids = await indexer.index_text(text, source_id="src-2")
        assert len(ids) > 0

    @pytest.mark.asyncio
    async def test_index_text_with_custom_chunker(self, indexer):
        """使用自定义 chunker"""
        from deepnovel.rag.chunker import TextChunker, ChunkStrategy

        chunker = TextChunker(
            strategy=ChunkStrategy.FIXED,
            chunk_size=20,
            min_chunk_size=1,
        )
        text = "abc def ghi jkl mno pqr stu vwx yz"
        ids = await indexer.index_text(text, chunker=chunker)
        assert len(ids) > 0

    @pytest.mark.asyncio
    async def test_get_stats(self, indexer):
        """统计信息正确"""
        chunks = [Chunk(content="测试", index=0)]
        await indexer.index_chunks(chunks)

        stats = await indexer.get_stats()
        assert stats["total_documents"] == 1
        assert stats["embedding_provider"] == "test"
        assert stats["embedding_dimension"] == 64

    @pytest.mark.asyncio
    async def test_delete_by_source(self, indexer):
        """按来源删除返回计数"""
        # delete_by_source 当前实现仅返回计数
        count = await indexer.delete_by_source("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_embedding_adapter_property(self, indexer):
        """embedding_adapter 属性"""
        assert indexer.embedding_adapter is not None
        assert indexer.embedding_adapter.dimension == 64

    @pytest.mark.asyncio
    async def test_vector_store_property(self, indexer):
        """vector_store 属性"""
        assert indexer.vector_store is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
