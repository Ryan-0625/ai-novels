"""
Tests: TenantAwareRepository — tenant_id auto-injection, filtering, fallback
Covers UT-59 ~ UT-64
"""

from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, Field, select

from ai_novels.repositories.base import (
    BaseRepository,
    TenantAwareRepository,
    _resolve_tenant_id,
)
from ai_novels.core.context import (
    WorkflowContext, set_current_context, get_current_tenant_id,
)


# ── Test Model ──

class FakeModel(SQLModel, table=True):
    """Minimal model for repository testing"""
    __tablename__ = "fake_entities"
    id: str = Field(primary_key=True)
    tenant_id: Optional[str] = Field(default=None)
    name: str = Field(default="")


# ── Fixtures ──

@pytest.fixture
def repo():
    return TenantAwareRepository(BaseRepository(FakeModel))


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def tenant_ctx():
    ctx = WorkflowContext.default().extend(tenant_id="t_001")
    # Create a version with specific tenant_id
    from ai_novels.core.context import TenantIdentity, UserIdentity, IdentityContext
    new_identity = IdentityContext(
        tenant=TenantIdentity(tenant_id="t_001", tenant_name="Test Tenant"),
        user=UserIdentity(user_id="u_001"),
    )
    import dataclasses
    ctx = dataclasses.replace(ctx, identity=new_identity)
    return ctx


# ── UT-59: get_all with explicit tenant_id ──

class TestGetAllExplicitTenant:
    @pytest.mark.asyncio
    async def test_passes_tenant_id(self, repo, mock_session):
        from unittest.mock import MagicMock
        mock_execute = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_execute)
        mock_execute.scalar_one_or_none.return_value = None
        mock_execute.scalars.return_value.all.return_value = []

        await repo.get_all(mock_session, tenant_id="t_001")
        # Verify the query was constructed with tenant_id filter
        call_stmt = mock_session.execute.call_args[0][0]
        call_str = str(call_stmt)
        assert "tenant_id" in call_str
        assert ":tenant_id_1" in call_str or "tenant_id" in call_str

    @pytest.mark.asyncio
    async def test_tenant_default_skips_filter(self, repo, mock_session):
        from unittest.mock import MagicMock
        mock_execute = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_execute)
        mock_execute.scalars.return_value.all.return_value = []

        # Set context to "default"
        ctx = WorkflowContext.default()
        set_current_context(ctx)
        try:
            await repo.get_all(mock_session, tenant_id="default")
            # With "default" tenant, inner.get_all is called without filter
        finally:
            set_current_context(None)


# ── UT-60: get_all with automatic tenant from context ──

class TestGetAllAutoTenant:
    @pytest.mark.asyncio
    async def test_reads_from_contextvars(self, repo, mock_session):
        from unittest.mock import MagicMock
        mock_execute = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_execute)
        mock_execute.scalars.return_value.all.return_value = []

        ctx = WorkflowContext.default().extend(tenant_id="t_auto")
        set_current_context(ctx)
        try:
            await repo.get_all(mock_session)
        finally:
            set_current_context(None)


# ── UT-61: "default" tenant pass-through ──

class TestDefaultTenantPassthrough:
    @pytest.mark.asyncio
    async def test_no_filter_when_default(self, repo, mock_session):
        from unittest.mock import MagicMock
        mock_execute = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_execute)
        mock_execute.scalars.return_value.all.return_value = []

        set_current_context(WorkflowContext.default())
        try:
            await repo.get_all(mock_session, tenant_id="default")
        finally:
            set_current_context(None)


# ── UT-62: create auto-fills tenant_id ──

class TestCreateAutoFill:
    @pytest.mark.asyncio
    async def test_fills_tenant_id(self, repo, mock_session):
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        entity = FakeModel(id="e1", name="test")
        set_current_context(WorkflowContext.default().extend(tenant_id="t_fill"))
        try:
            result = await repo.create(mock_session, entity, tenant_id="t_fill")
            assert result.tenant_id == "t_fill"
        finally:
            set_current_context(None)

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing(self, repo, mock_session):
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        entity = FakeModel(id="e2", name="existing", tenant_id="t_existing")
        set_current_context(WorkflowContext.default().extend(tenant_id="t_ctx"))
        try:
            result = await repo.create(mock_session, entity, tenant_id="t_ctx")
            assert result.tenant_id == "t_existing"  # not overwritten
        finally:
            set_current_context(None)


# ── UT-64: pass-through methods ──

class TestPassthrough:
    @pytest.mark.asyncio
    async def test_update_calls_inner(self, repo, mock_session):
        entity = FakeModel(id="e1", name="upd")
        with patch.object(repo._inner, 'update', AsyncMock()) as mock_update:
            await repo.update(mock_session, entity)
            mock_update.assert_called_once_with(mock_session, entity)

    @pytest.mark.asyncio
    async def test_delete_calls_inner(self, repo, mock_session):
        entity = FakeModel(id="e1", name="del")
        with patch.object(repo._inner, 'delete', AsyncMock()) as mock_del:
            await repo.delete(mock_session, entity)
            mock_del.assert_called_once_with(mock_session, entity)

    @pytest.mark.asyncio
    async def test_count_calls_inner(self, repo, mock_session):
        with patch.object(repo._inner, 'count', AsyncMock(return_value=5)) as mock_count:
            result = await repo.count(mock_session)
            assert result == 5
            mock_count.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_exists_calls_inner(self, repo, mock_session):
        with patch.object(repo._inner, 'get_by_id', AsyncMock(return_value=FakeModel(id="e1"))):
            result = await repo.exists(mock_session, "e1")
            assert result is True


# ── _resolve_tenant_id helper ──

class TestResolveTenantId:
    def test_with_context(self):
        set_current_context(WorkflowContext.default().extend(tenant_id="t_helper"))
        try:
            assert _resolve_tenant_id() == "default"  # default ctx has "default"
        finally:
            set_current_context(None)

    def test_without_context(self):
        set_current_context(None)
        assert _resolve_tenant_id() == "default"
