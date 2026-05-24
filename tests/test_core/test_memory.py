"""
Tests: WorkingMemoryBackend — LRU isolation, thread safety, eviction
"""

import pytest
from ai_novels.core.memory import WorkingMemoryBackend, MemoryType
from ai_novels.core.context import MemoryScope


@pytest.fixture
def scope_a():
    return MemoryScope(tenant_id="t1", session_id="s1", agent_name="agent1")

@pytest.fixture
def scope_b():
    return MemoryScope(tenant_id="t2", session_id="s1", agent_name="agent1")


@pytest.mark.asyncio
async def test_save_and_load():
    mem = WorkingMemoryBackend(max_size_per_scope=100)
    scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

    saved = await mem.save(scope, "key1", "value1")
    assert saved is True

    val = await mem.load(scope, "key1")
    assert val == "value1"


@pytest.mark.asyncio
async def test_tenant_isolation():
    mem = WorkingMemoryBackend(max_size_per_scope=100)

    await mem.save(scope_a, "shared_key", "tenant_a_value")
    await mem.save(scope_b, "shared_key", "tenant_b_value")

    val_a = await mem.load(scope_a, "shared_key")
    val_b = await mem.load(scope_b, "shared_key")

    assert val_a == "tenant_a_value"
    assert val_b == "tenant_b_value"
    assert val_a != val_b


@pytest.mark.asyncio
async def test_lru_eviction():
    mem = WorkingMemoryBackend(max_size_per_scope=3)
    scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

    await mem.save(scope, "k1", 1)
    await mem.save(scope, "k2", 2)
    await mem.save(scope, "k3", 3)
    # Access k1 to make it recently used
    await mem.load(scope, "k1")
    # k4 should evict k2 (least recently used after k1 access)
    await mem.save(scope, "k4", 4)

    assert await mem.load(scope, "k1") == 1  # should exist
    assert await mem.load(scope, "k4") == 4  # should exist
    # k2 was evicted
    assert await mem.load(scope, "k2") is None  # evicted


@pytest.mark.asyncio
async def test_search():
    mem = WorkingMemoryBackend(max_size_per_scope=100)
    scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

    await mem.save(scope, "user_preference", "dark_mode")
    await mem.save(scope, "user_name", "Alice")
    await mem.save(scope, "chapter_theme", "adventure")

    results = await mem.search(scope, "user")
    assert len(results) >= 2
    keys = {r.key for r in results}
    assert "user_preference" in keys
    assert "user_name" in keys


@pytest.mark.asyncio
async def test_delete():
    mem = WorkingMemoryBackend(max_size_per_scope=100)
    scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

    await mem.save(scope, "key1", "val")
    assert await mem.delete(scope, "key1") is True
    assert await mem.load(scope, "key1") is None
    assert await mem.delete(scope, "nonexistent") is False


@pytest.mark.asyncio
async def test_clear_scope():
    mem = WorkingMemoryBackend(max_size_per_scope=100)

    await mem.save(scope_a, "k1", 1)
    await mem.save(scope_a, "k2", 2)
    await mem.save(scope_b, "k3", 3)

    cleared = await mem.clear_scope(scope_a)
    assert cleared == 2

    assert await mem.load(scope_a, "k1") is None
    # scope_b should still exist
    assert await mem.load(scope_b, "k3") == 3


@pytest.mark.asyncio
async def test_concurrent_access():
    """100 concurrent writes — no data races"""
    import asyncio
    mem = WorkingMemoryBackend(max_size_per_scope=500)
    scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

    async def writer(i):
        await mem.save(scope, f"key_{i}", i)

    tasks = [writer(i) for i in range(100)]
    await asyncio.gather(*tasks)

    for i in range(100):
        val = await mem.load(scope, f"key_{i}")
        assert val == i, f"key_{i} expected {i} got {val}"
