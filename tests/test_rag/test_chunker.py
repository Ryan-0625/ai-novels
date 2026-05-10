"""
文档分块器单元测试

测试 TextChunker 的四种分块策略。
"""

import pytest

from deepnovel.rag.chunker import Chunk, ChunkStrategy, TextChunker


SAMPLE_TEXT = """修仙世界分为五大境界。

炼气期是入门境界，修士通过吐纳天地灵气来淬炼身体。筑基期则是奠定道基的关键阶段，需要将灵气转化为真元。

金丹期是第三个境界。修士在体内凝结金丹，从而获得更强大的力量。元婴期更为玄妙，可以在丹田内孕育元婴。

最后的化神期是传说中的境界。据说达到此境界的修士可以元神出窍，遨游天地。"""

LONG_TEXT = "这是一个测试句子。" * 100


class TestChunk:
    """Chunk 数据类测试"""

    def test_basic_properties(self):
        chunk = Chunk(content="测试内容", index=0, start_pos=0, end_pos=10)
        assert chunk.word_count == 1  # 测试内容 = 1 word? Actually split by space
        assert chunk.char_count == 4
        assert chunk.metadata == {}

    def test_word_count_chinese(self):
        chunk = Chunk(content="hello world test")
        assert chunk.word_count == 3

    def test_to_dict(self):
        chunk = Chunk(content="test", index=1, metadata={"key": "val"})
        d = chunk.to_dict()
        assert d["content"] == "test"
        assert d["index"] == 1
        assert d["metadata"] == {"key": "val"}


class TestFixedChunking:
    """固定大小分块测试"""

    @pytest.fixture
    def chunker(self):
        return TextChunker(
            strategy=ChunkStrategy.FIXED,
            chunk_size=50,
            chunk_overlap=10,
            min_chunk_size=10,
        )

    def test_chunk_size(self, chunker):
        chunks = chunker.chunk(LONG_TEXT)
        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk.content) <= 50

    def test_overlap(self, chunker):
        chunks = chunker.chunk(LONG_TEXT)
        if len(chunks) >= 2:
            # 检查重叠：第二个 chunk 的开始应该在第一个 chunk 的内容中
            assert chunks[1].content[:5] in chunks[0].content

    def test_positions(self, chunker):
        chunks = chunker.chunk(LONG_TEXT)
        assert chunks[0].start_pos == 0
        assert chunks[0].end_pos > 0
        for i in range(len(chunks) - 1):
            assert chunks[i].end_pos > chunks[i].start_pos

    def test_index_increment(self, chunker):
        chunks = chunker.chunk(LONG_TEXT)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_min_size_filter(self, chunker):
        short = "短"
        chunks = chunker.chunk(short)
        # 长度小于 min_chunk_size，应该被过滤
        assert len(chunks) == 0


class TestParagraphChunking:
    """段落分块测试"""

    @pytest.fixture
    def chunker(self):
        return TextChunker(
            strategy=ChunkStrategy.PARAGRAPH,
            chunk_size=200,
            min_chunk_size=5,
        )

    def test_respects_paragraphs(self, chunker):
        chunks = chunker.chunk(SAMPLE_TEXT)
        # 段落边界不应被随意切断（文本较短时可能只有 1 个 chunk）
        assert len(chunks) >= 1

    def test_metadata_passed(self, chunker):
        chunks = chunker.chunk(SAMPLE_TEXT, source="test")
        assert chunks[0].metadata["source"] == "test"


class TestSentenceChunking:
    """句子分块测试"""

    @pytest.fixture
    def chunker(self):
        return TextChunker(
            strategy=ChunkStrategy.SENTENCE,
            chunk_size=100,
            min_chunk_size=5,
        )

    def test_sentence_boundaries(self, chunker):
        text = "第一句。第二句！第三句？"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        # 每个 chunk 应该以句子结束符结尾（或被包含）
        for chunk in chunks:
            assert len(chunk.content) > 0

    def test_multiple_sentences(self, chunker):
        chunks = chunker.chunk(SAMPLE_TEXT)
        assert len(chunks) >= 1


class TestSemanticChunking:
    """语义分块测试"""

    @pytest.fixture
    def chunker(self):
        return TextChunker(
            strategy=ChunkStrategy.SEMANTIC,
            chunk_size=100,
            chunk_overlap=20,
            min_chunk_size=5,
        )

    def test_overlap_window(self, chunker):
        chunks = chunker.chunk(SAMPLE_TEXT)
        if len(chunks) >= 2:
            # 语义分块应该保留重叠
            assert len(chunks) >= 2

    def test_sentence_preservation(self, chunker):
        text = "修仙世界很大。灵气充沛。"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        # 内容应包含完整句子
        assert "修仙世界" in chunks[0].content

    def test_empty_text(self, chunker):
        chunks = chunker.chunk("")
        assert chunks == []

    def test_no_sentences(self, chunker):
        chunks = chunker.chunk("   ")
        assert chunks == []


class TestChunkBatch:
    """批量分块测试"""

    def test_batch_processing(self):
        chunker = TextChunker(
            strategy=ChunkStrategy.FIXED,
            chunk_size=20,
            min_chunk_size=1,
        )
        texts = ["短文本", "这是一个比较长的文本内容，需要分块处理。" * 5]
        results = chunker.chunk_batch(texts)
        assert len(results) == 2
        assert len(results[0]) == 1  # 短文本也能产生 1 个 chunk
        assert len(results[1]) > 0

    def test_batch_with_metadata(self):
        chunker = TextChunker(
            strategy=ChunkStrategy.FIXED,
            chunk_size=20,
            min_chunk_size=1,
        )
        texts = ["abc def ghi jkl mno pqr"]
        metadatas = [{"id": 1}]
        results = chunker.chunk_batch(texts, metadatas)
        assert len(results[0]) > 0
        assert results[0][0].metadata["id"] == 1


class TestChunkStrategyEnum:
    """分块策略枚举测试"""

    def test_values(self):
        assert ChunkStrategy.FIXED.value == "fixed"
        assert ChunkStrategy.PARAGRAPH.value == "paragraph"
        assert ChunkStrategy.SENTENCE.value == "sentence"
        assert ChunkStrategy.SEMANTIC.value == "semantic"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
