"""
Tests: WorkingMemoryBackend + MemoryManager — LRU, isolation, thread safety, fuse, MemoryEntry DTO
Covers UT-32 ~ UT-43
"""

import asyncio
from datetime import datetime, timezone

import pytest
from dataclasses import dataclass

from ai_novels.core.memory import (
    WorkingMemoryBackend, MemoryManager, MemoryEntry,
    MemorySearchResult, MemoryBackendUnavailable,
    init_memory_manager, get_memory_manager,
)
from ai_novels.core.context import MemoryScope, MemoryType


@pytest.fixture
def scope_a():
    return MemoryScope(tenant_id="t1", session_id="s1", agent_name="agent1")


@pytest.fixture
def scope_b():
    return MemoryScope(tenant_id="t2", session_id="s1", agent_name="agent1")


# ── UT-32: save + load ──

class TestWorkingMemorySaveLoad:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        saved = await mem.save(scope, "key1", "value1")
        assert saved is True
        val = await mem.load(scope, "key1")
        assert val == "value1"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        assert await mem.load(scope, "nonexistent") is None

    @pytest.mark.asyncio
    async def test_overwrite(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "k", "old")
        await mem.save(scope, "k", "new")
        assert await mem.load(scope, "k") == "new"

    @pytest.mark.asyncio
    async def test_complex_value(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        val = {"nested": {"list": [1, 2, 3]}, "bool": True, "num": 42}
        await mem.save(scope, "complex", val)
        assert await mem.load(scope, "complex") == val


# ── UT-33: tenant isolation ──

class TestTenantIsolation:
    @pytest.mark.asyncio
    async def test_different_tenants(self, scope_a, scope_b):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        await mem.save(scope_a, "key", "tenant_a_value")
        await mem.save(scope_b, "key", "tenant_b_value")
        assert await mem.load(scope_a, "key") == "tenant_a_value"
        assert await mem.load(scope_b, "key") == "tenant_b_value"

    @pytest.mark.asyncio
    async def test_different_sessions(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        s1 = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        s2 = MemoryScope(tenant_id="t1", session_id="s2", agent_name="a1")
        await mem.save(s1, "k", "from_s1")
        await mem.save(s2, "k", "from_s2")
        assert await mem.load(s1, "k") == "from_s1"
        assert await mem.load(s2, "k") == "from_s2"

    @pytest.mark.asyncio
    async def test_different_agents(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        a1 = MemoryScope(tenant_id="t1", session_id="s1", agent_name="agent_a")
        a2 = MemoryScope(tenant_id="t1", session_id="s1", agent_name="agent_b")
        await mem.save(a1, "k", "from_a")
        await mem.save(a2, "k", "from_b")
        assert await mem.load(a1, "k") == "from_a"
        assert await mem.load(a2, "k") == "from_b"


# ── UT-34: LRU eviction ──

class TestLRUEviction:
    @pytest.mark.asyncio
    async def test_evicts_least_recently_used(self):
        mem = WorkingMemoryBackend(max_size_per_scope=3)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "k1", 1)
        await mem.save(scope, "k2", 2)
        await mem.save(scope, "k3", 3)
        await mem.load(scope, "k1")  # access k1 → becomes MRU
        await mem.save(scope, "k4", 4)  # evicts k2 (LRU)
        assert await mem.load(scope, "k1") == 1
        assert await mem.load(scope, "k4") == 4
        assert await mem.load(scope, "k2") is None

    @pytest.mark.asyncio
    async def test_no_eviction_below_limit(self):
        mem = WorkingMemoryBackend(max_size_per_scope=3)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "k1", 1)
        await mem.save(scope, "k2", 2)
        assert await mem.load(scope, "k1") == 1
        assert await mem.load(scope, "k2") == 2


# ── UT-35: search ──

class TestSearch:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "user_pref", "value")
        results = await mem.search(scope, "user_pref")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_partial_match(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "chapter_theme_dark", "value")
        results = await mem.search(scope, "dark")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_limit(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        for i in range(10):
            await mem.save(scope, f"key_{i}", f"val_{i}")
        results = await mem.search(scope, "key", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_no_match(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "aaa", 1)
        results = await mem.search(scope, "zzz")
        assert len(results) == 0


# ── UT-36: delete ──

class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "k", "v")
        assert await mem.delete(scope, "k") is True
        assert await mem.load(scope, "k") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        assert await mem.delete(scope, "nonexistent") is False

    @pytest.mark.asyncio
    async def test_delete_twice(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")
        await mem.save(scope, "k", "v")
        await mem.delete(scope, "k")
        assert await mem.delete(scope, "k") is False


# ── UT-37: clear_scope ──

class TestClearScope:
    @pytest.mark.asyncio
    async def test_clear_returns_count(self, scope_a, scope_b):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        await mem.save(scope_a, "k1", 1)
        await mem.save(scope_a, "k2", 2)
        await mem.save(scope_b, "k3", 3)
        assert await mem.clear_scope(scope_a) == 2

    @pytest.mark.asyncio
    async def test_clear_isolates_other_tenants(self, scope_a, scope_b):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        await mem.save(scope_a, "k1", 1)
        await mem.save(scope_b, "k3", 3)
        await mem.clear_scope(scope_a)
        assert await mem.load(scope_a, "k1") is None
        assert await mem.load(scope_b, "k3") == 3

    @pytest.mark.asyncio
    async def test_clear_empty_scope(self):
        mem = WorkingMemoryBackend(max_size_per_scope=100)
        scope = MemoryScope(tenant_id="t_new", session_id="s_new", agent_name="a_new")
        assert await mem.clear_scope(scope) == 0


# ── UT-38: concurrent access ──

class TestConcurrency:
    @pytest.mark.asyncio
    async def test_100_concurrent_writes(self):
        mem = WorkingMemoryBackend(max_size_per_scope=500)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

        async def writer(i):
            await mem.save(scope, f"key_{i}", i)

        await asyncio.gather(*[writer(i) for i in range(100)])

        for i in range(100):
            val = await mem.load(scope, f"key_{i}")
            assert val == i, f"key_{i} expected {i} got {val}"

    @pytest.mark.asyncio
    async def test_concurrent_read_write(self):
        mem = WorkingMemoryBackend(max_size_per_scope=500)
        scope = MemoryScope(tenant_id="t1", session_id="s1", agent_name="a1")

        async def reader_writer(i):
            if i % 2 == 0:
                await mem.save(scope, "shared", i)
            return await mem.load(scope, "shared")

        results = await asyncio.gather(*[reader_writer(i) for i in range(50)])
        assert any(r is not None for r in results)


# ── UT-39: MemoryEntry DTO ──

class TestMemoryEntryDTO:
    def test_timestamp_auto_generated(self):
        entry = MemoryEntry(
            key="k", value="v", memory_type=MemoryType.WORKING,
            tenant_id="t1", agent_name="a1", session_id="s1",
        )
        assert entry.timestamp is not None
        assert isinstance(entry.timestamp, datetime)
        # Should be very close to now
        diff = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
        assert diff < 5

    def test_default_ttl_none(self):
        entry = MemoryEntry(
            key="k", value="v", memory_type=MemoryType.WORKING,
            tenant_id="t1", agent_name="a1", session_id="s1",
        )
        assert entry.ttl_seconds is None

    def test_default_metadata_empty(self):
        entry = MemoryEntry(
            key="k", value="v", memory_type=MemoryType.WORKING,
            tenant_id="t1", agent_name="a1", session_id="s1",
        )
        assert entry.metadata == {}
        assert entry.embedding is None

    def test_full_initialization(self):
        entry = MemoryEntry(
            key="k", value="v", memory_type=MemoryType.LONG_TERM,
            tenant_id="t1", agent_name="a1", session_id="s1",
            ttl_seconds=3600, metadata={"source": "test"},
            embedding=[0.1, 0.2, 0.3],
        )
        assert entry.ttl_seconds == 3600
        assert entry.metadata == {"source": "test"}
        assert entry.embedding == [0.1, 0.2, 0.3]


# ── UT-40: MemorySearchResult defaults ──

class TestMemorySearchResult:
    def test_defaults(self):
        r = MemorySearchResult(key="k", value="v")
        assert r.score == 1.0
        assert r.memory_type == MemoryType.LONG_TERM
        assert r.source == ""


# ── UT-41: fuse with single backend failure ──

class TestMemoryManagerFuse:
    @pytest.mark.asyncio
    async def test_fuse_short_fails_long_ok(self, scope_a):
        """When short backend fails, fuse returns long results"""
        working = WorkingMemoryBackend(max_size_per_scope=100)

        class FakeShort:
            async def save(self, *a, **kw): return True
            async def load(self, *a, **kw): return None
            async def search(self, *a, **kw):
                raise MemoryBackendUnavailable("short_term")
            async def delete(self, *a, **kw): return True
            async def clear_scope(self, *a, **kw): return 0

        class FakeLong:
            def __init__(self):
                self.saved = []
            async def save(self, scope, key, value, ttl=None, tags=None):
                self.saved.append((scope, key, value))
                return True
            async def load(self, *a, **kw): return None
            async def search(self, scope, query, limit=5):
                return [MemorySearchResult(key="k1", value="long_val", score=0.9)]
            async def delete(self, *a, **kw): return True
            async def clear_scope(self, *a, **kw): return 0

        mm = MemoryManager(working, FakeShort(), FakeLong())
        results = await mm.fuse(scope_a, "query")
        assert len(results) >= 1
        assert any(r.value == "long_val" for r in results)

    @pytest.mark.asyncio
    async def test_fuse_both_fail_return_empty(self, scope_a):
        working = WorkingMemoryBackend(max_size_per_scope=100)

        class AlwaysFail:
            async def search(self, *a, **kw):
                raise MemoryBackendUnavailable("backend")

        mm = MemoryManager(working, AlwaysFail(), AlwaysFail())
        results = await mm.fuse(scope_a, "query")
        assert results == []

    @pytest.mark.asyncio
    async def test_fuse_deduplicates(self, scope_a):
        """UT-42: same key from short and long — short wins"""
        working = WorkingMemoryBackend(max_size_per_scope=100)

        class FakeShort:
            async def search(self, scope, query, limit=5):
                return [MemorySearchResult(key="k1", value="short_val", score=0.9)]

        class FakeLong:
            async def search(self, scope, query, limit=5):
                return [MemorySearchResult(key="k1", value="long_val", score=0.8)]

        mm = MemoryManager(working, FakeShort(), FakeLong())
        results = await mm.fuse(scope_a, "query")
        assert len(results) == 1
        assert results[0].value == "short_val"  # short prioritized


# ── UT-43: init_memory_manager singleton ──

class TestInitMemoryManager:
    @pytest.mark.asyncio
    async def test_init_once(self):
        w = WorkingMemoryBackend(max_size_per_scope=10)
        mm1 = init_memory_manager(w, w, w)
        mm2 = init_memory_manager(w, w, w)
        assert mm1 is mm2  # same instance

    @pytest.mark.asyncio
    async def test_get_before_init_raises(self):
        import ai_novels.core.memory as mem_mod
        mem_mod._memory_manager = None
        with pytest.raises(Exception, match="not initialized"):
            get_memory_manager()
