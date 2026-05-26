"""
Tests: TenantSessionFactory �?shared/isolated pool, init guard, close_all
Covers UT-65 ~ UT-70
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ai_novels.database.tenant_session import (
    TenantSessionFactory,
    init_tenant_session_factory,
    get_tenant_session_factory,
    get_tenant_session,
)
from ai_novels.core.context import (
    WorkflowContext, TenantTier, TenantIdentity,
    UserIdentity, IdentityContext, ExecutionContext, MemoryScope,
)


@pytest.fixture
def factory():
    return TenantSessionFactory(
        shared_dsn="postgresql+asyncpg://test:test@localhost:33432/test",
        shared_pool_size=5,
        shared_max_overflow=2,
    )


@pytest.fixture
def enterprise_ctx():
    identity = IdentityContext(
        tenant=TenantIdentity(tenant_id="t_ent", tier=TenantTier.ENTERPRISE),
        user=UserIdentity(user_id="u_001"),
    )
    return WorkflowContext(
        identity=identity,
        execution=ExecutionContext(trace_id="trace_x"),
        memory=MemoryScope(tenant_id="t_ent", session_id="s1", agent_name="a1"),
    )


@pytest.fixture
def free_ctx():
    identity = IdentityContext(
        tenant=TenantIdentity(tenant_id="t_free", tier=TenantTier.FREE),
        user=UserIdentity(user_id="u_002"),
    )
    return WorkflowContext(
        identity=identity,
        execution=ExecutionContext(trace_id="trace_y"),
        memory=MemoryScope(tenant_id="t_free", session_id="s2", agent_name="a2"),
    )


# ── UT-65: Shared pool ──

class TestSharedPool:
    @pytest.mark.asyncio
    async def test_returns_shared_session_without_ctx(self, factory):
        session = await factory.get_session(None)
        assert session is not None

    @pytest.mark.asyncio
    async def test_returns_shared_session_for_free(self, factory, free_ctx):
        session = await factory.get_session(free_ctx)
        assert session is not None


# ── UT-66: Enterprise isolated pool ──

class TestEnterpriseIsolatedPool:
    @pytest.mark.asyncio
    async def test_returns_isolated_when_registered(self, factory, enterprise_ctx):
        factory.register_isolated_tenant("t_ent", "postgresql+asyncpg://ent:pass@localhost:33432/ent")
        session = await factory.get_session(enterprise_ctx)
        assert session is not None

    @pytest.mark.asyncio
    async def test_returns_shared_when_not_registered(self, factory, enterprise_ctx):
        # Enterprise tenant but no isolated pool registered
        session = await factory.get_session(enterprise_ctx)
        assert session is not None

    @pytest.mark.asyncio
    async def test_register_isolated_adds_maker(self, factory):
        factory.register_isolated_tenant("t_new", "postgresql+asyncpg://new:pass@localhost:33432/new")
        assert "t_new" in factory._isolated_makers


# ── UT-67: Enterprise not registered �?shared ──

class TestEnterpriseFallback:
    @pytest.mark.asyncio
    async def test_fallback_to_shared(self, factory, enterprise_ctx):
        session = await factory.get_session(enterprise_ctx)
        # Should return shared session, not crash
        assert session is not None


# ── UT-68: init_tenant_session_factory double-checked locking ──

class TestInitDoubleCheckedLocking:
    @pytest.mark.asyncio
    async def test_init_twice_returns_same(self):
        from ai_novels.database import tenant_session as ts
        ts._session_factory = None

        f1 = await init_tenant_session_factory("postgresql+asyncpg://test:test@localhost:33432/test")
        f2 = await init_tenant_session_factory("postgresql+asyncpg://test:test@localhost:33432/test")
        assert f1 is f2

    @pytest.mark.asyncio
    async def test_init_concurrent(self):
        from ai_novels.database import tenant_session as ts
        ts._session_factory = None

        async def init():
            return await init_tenant_session_factory(
                "postgresql+asyncpg://test:test@localhost:33432/test"
            )

        import asyncio
        results = await asyncio.gather(init(), init(), init())
        # All return the same instance
        assert results[0] is results[1]
        assert results[1] is results[2]


# ── UT-69: get_factory before init ──

class TestGetFactoryBeforeInit:
    def test_raises_if_not_initialized(self):
        from ai_novels.database import tenant_session as ts
        ts._session_factory = None
        with pytest.raises(Exception, match="not initialized"):
            get_tenant_session_factory()


# ── UT-70: close_all ──

class TestCloseAll:
    @pytest.mark.asyncio
    async def test_close_all_disposes_all(self, factory):
        factory.register_isolated_tenant("t1", "postgresql+asyncpg://t1:pass@localhost:33432/t1")
        factory.register_isolated_tenant("t2", "postgresql+asyncpg://t2:pass@localhost:33432/t2")

        mock_shared = MagicMock()
        mock_shared.dispose = AsyncMock()
        with patch.object(factory, '_shared_engine', mock_shared):
            with patch.object(factory, '_isolated_makers', {
                "t1": MagicMock(),
                "t2": MagicMock(),
            }):
                await factory.close_all()
                mock_shared.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all_clears_makers(self, factory):
        factory.register_isolated_tenant("t1", "postgresql+asyncpg://t1:pass@localhost:33432/t1")
        await factory.close_all()
        assert len(factory._isolated_makers) == 0

    @pytest.mark.asyncio
    async def test_close_all_with_no_isolated(self, factory):
        mock_shared = MagicMock()
        mock_shared.dispose = AsyncMock()
        with patch.object(factory, '_shared_engine', mock_shared):
            await factory.close_all()
            mock_shared.dispose.assert_called_once()
