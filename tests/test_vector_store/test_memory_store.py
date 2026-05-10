"""
InMemoryVectorStore 单元测试

测试范围:
- connect / disconnect / health_check
- upsert 批量插入
- search 语义搜索
- delete 删除
- get 按ID获取
- count 计数
- clear 清空
- 过滤条件
"""

import pytest

from deepnovel.vector_store.enhanced_base import VectorDocument
from deepnovel.vector_store.memory_store import InMemoryVectorStore


class TestInMemoryVectorStore:
    """InMemoryVectorStore 测试"""

    @pytest.fixture
    async def store(self):
        """创建并连接内存向量存储"""
        s = InMemoryVectorStore(collection_name="test")
        await s.connect()
        yield s
        await s.clear()

    @pytest.mark.asyncio
    async def test_connect(self):
        """connect 必须成功"""
        s = InMemoryVectorStore()
        result = await s.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_connected(self, store):
        """连接后健康检查必须返回 True"""
        assert await store.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """断开连接后健康检查必须返回 False"""
        s = InMemoryVectorStore()
        assert await s.health_check() is False

    @pytest.mark.asyncio
    async def test_upsert_and_count(self, store):
        """upsert 后 count 必须正确"""
        docs = [
            VectorDocument(id="d1", content="hello world"),
            VectorDocument(id="d2", content="python programming"),
        ]
        count = await store.upsert(docs)
        assert count == 2
        assert await store.count() == 2

    @pytest.mark.asyncio
    async def test_upsert_batch_size(self, store):
        """batch_size 必须限制处理数量"""
        docs = [
            VectorDocument(id=f"d{i}", content=f"doc {i}")
            for i in range(10)
        ]
        count = await store.upsert(docs, batch_size=5)
        assert count == 5

    @pytest.mark.asyncio
    async def test_search_basic(self, store):
        """search 必须返回相似文档"""
        docs = [
            VectorDocument(id="d1", content="machine learning"),
            VectorDocument(id="d2", content="deep learning"),
            VectorDocument(id="d3", content="cooking recipes"),
        ]
        await store.upsert(docs)

        results = await store.search("neural networks", top_k=2)
        assert len(results) == 2
        # 机器学习相关文档应该排在前面
        assert results[0].score > 0

    @pytest.mark.asyncio
    async def test_search_with_filters(self, store):
        """search 过滤条件必须生效"""
        docs = [
            VectorDocument(id="d1", content="python guide", metadata={"category": "tech"}),
            VectorDocument(id="d2", content="cooking guide", metadata={"category": "food"}),
        ]
        await store.upsert(docs)

        results = await store.search("guide", filters={"category": "tech"})
        assert len(results) == 1
        assert results[0].id == "d1"

    @pytest.mark.asyncio
    async def test_get_by_ids(self, store):
        """get 必须按ID返回文档"""
        docs = [
            VectorDocument(id="d1", content="content one"),
            VectorDocument(id="d2", content="content two"),
        ]
        await store.upsert(docs)

        result = await store.get(["d1"])
        assert len(result) == 1
        assert result[0].id == "d1"

    @pytest.mark.asyncio
    async def test_get_missing_ids(self, store):
        """get 不存在的ID必须返回空列表"""
        result = await store.get(["not-exist"])
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_by_ids(self, store):
        """delete 必须删除指定文档"""
        docs = [
            VectorDocument(id="d1", content="delete me"),
            VectorDocument(id="d2", content="keep me"),
        ]
        await store.upsert(docs)

        deleted = await store.delete(["d1"])
        assert deleted == 1
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_delete_with_filters(self, store):
        """delete 过滤条件必须生效"""
        docs = [
            VectorDocument(id="d1", content="a", metadata={"tag": "old"}),
            VectorDocument(id="d2", content="b", metadata={"tag": "new"}),
        ]
        await store.upsert(docs)

        deleted = await store.delete(["d1", "d2"], filters={"tag": "old"})
        assert deleted == 1
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_count_with_filters(self, store):
        """count 过滤条件必须生效"""
        docs = [
            VectorDocument(id="d1", content="a", metadata={"status": "active"}),
            VectorDocument(id="d2", content="b", metadata={"status": "inactive"}),
            VectorDocument(id="d3", content="c", metadata={"status": "active"}),
        ]
        await store.upsert(docs)

        assert await store.count() == 3
        assert await store.count(filters={"status": "active"}) == 2

    @pytest.mark.asyncio
    async def test_clear(self, store):
        """clear 必须清空所有文档"""
        docs = [VectorDocument(id="d1", content="test")]
        await store.upsert(docs)
        assert await store.count() == 1

        result = await store.clear()
        assert result is True
        assert await store.count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
