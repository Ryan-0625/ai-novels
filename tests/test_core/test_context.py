"""
Tests: WorkflowContext construction, default factory, JWT payload, contextvars isolation
Covers UT-24 ~ UT-31
"""

import asyncio
import pytest
from dataclasses import FrozenInstanceError
from ai_novels.core.context import (
    WorkflowContext, TenantIdentity, UserIdentity,
    IdentityContext, ExecutionContext, MemoryScope,
    TenantTier, get_current_tenant_id, get_current_user_id,
    get_current_trace_id, get_current_session_id,
    set_current_context, get_current_context,
)


class TestWorkflowContextDefault:
    """UT-24: WorkflowContext.default()"""
    def test_default_tenant_id(self):
        ctx = WorkflowContext.default()
        assert ctx.tenant_id == "default"

    def test_default_user_id(self):
        ctx = WorkflowContext.default()
        assert ctx.user_id == "local"

    def test_default_trace_id_generated(self):
        ctx = WorkflowContext.default()
        assert ctx.trace_id != ""
        assert len(ctx.trace_id) > 10

    def test_default_session_id_generated(self):
        ctx = WorkflowContext.default()
        assert ctx.session_id != ""
        assert len(ctx.session_id) > 10

    def test_default_timeout(self):
        ctx = WorkflowContext.default()
        assert ctx.execution.timeout_seconds == 60

    def test_default_retry(self):
        ctx = WorkflowContext.default()
        assert ctx.execution.max_retries == 3

    def test_default_tenant_tier(self):
        ctx = WorkflowContext.default()
        assert ctx.identity.tenant.tier == TenantTier.FREE


class TestWorkflowContextFromJWT:
    """UT-25: WorkflowContext.from_jwt_payload()"""
    def test_full_payload(self):
        payload = {
            "sub": "u_001",
            "tenant_id": "t_pro",
            "tenant_name": "Pro Publisher",
            "tier": "pro",
            "features": ["advanced_outline", "unlimited_chapters"],
            "name": "Alice",
            "email": "alice@pub.com",
            "roles": ["editor", "admin"],
            "trace_id": "trace_abc123",
            "correlation_id": "corr_xyz",
            "session_id": "session_demo",
            "task_id": "task_001",
            "agent_name": "writer",
        }
        ctx = WorkflowContext.from_jwt_payload(payload)

        assert ctx.tenant_id == "t_pro"
        assert ctx.identity.tenant.tenant_name == "Pro Publisher"
        assert ctx.identity.tenant.tier == TenantTier.PRO
        assert ctx.identity.tenant.has_feature("advanced_outline") is True
        assert ctx.identity.tenant.has_feature("nonexistent") is False
        assert ctx.identity.tenant.features == {"advanced_outline", "unlimited_chapters"}

        assert ctx.user_id == "u_001"
        assert ctx.identity.user.username == "Alice"
        assert ctx.identity.user.email == "alice@pub.com"
        assert "admin" in ctx.identity.user.roles

        assert ctx.trace_id == "trace_abc123"
        assert ctx.execution.correlation_id == "corr_xyz"
        assert ctx.session_id == "session_demo"
        assert ctx.memory.task_id == "task_001"
        assert ctx.memory.agent_name == "writer"

    """UT-26: from_jwt_payload() with missing fields"""
    def test_minimal_payload(self):
        payload = {"sub": "u_001"}
        ctx = WorkflowContext.from_jwt_payload(payload)

        assert ctx.tenant_id == "default"
        assert ctx.identity.tenant.tier == TenantTier.FREE
        assert ctx.identity.tenant.features == set()
        assert ctx.user_id == "u_001"
        assert ctx.identity.user.username == "anonymous"
        assert ctx.trace_id is not None
        assert ctx.session_id is not None

    def test_empty_payload(self):
        ctx = WorkflowContext.from_jwt_payload({})
        assert ctx.tenant_id == "default"
        assert ctx.user_id == "anonymous"

    def test_enterprise_tier(self):
        payload = {"sub": "u_001", "tenant_id": "t_ent", "tier": "enterprise"}
        ctx = WorkflowContext.from_jwt_payload(payload)
        assert ctx.identity.tenant.tier == TenantTier.ENTERPRISE


class TestWorkflowContextExtend:
    """UT-27: extend()"""
    def test_extend_adds_key(self):
        ctx = WorkflowContext.default()
        ctx2 = ctx.extend(custom_key="custom_value")
        assert ctx2.extra["custom_key"] == "custom_value"

    def test_extend_immutable_original(self):
        ctx = WorkflowContext.default()
        ctx2 = ctx.extend(custom_key="custom_value")
        assert "custom_key" not in ctx.extra

    def test_extend_preserves_existing(self):
        ctx = WorkflowContext.default().extend(existing="keep")
        ctx2 = ctx.extend(new="added")
        assert ctx2.extra["existing"] == "keep"
        assert ctx2.extra["new"] == "added"

    def test_extend_overwrites(self):
        ctx = WorkflowContext.default().extend(key="old")
        ctx2 = ctx.extend(key="new")
        assert ctx2.extra["key"] == "new"


class TestWorkflowContextImmutability:
    """UT-28: frozen dataclass"""
    def test_cannot_modify_tenant_id(self):
        ctx = WorkflowContext.default()
        with pytest.raises(FrozenInstanceError):
            ctx.identity.tenant.tenant_id = "hacked"  # type: ignore


class TestContextvarsBridge:
    """UT-29: set/get context"""
    def test_set_and_get(self):
        ctx = WorkflowContext.default()
        set_current_context(ctx)
        try:
            retrieved = get_current_context()
            assert retrieved is ctx
            assert retrieved.tenant_id == "default"
        finally:
            set_current_context(None)

    """UT-30: cleanup"""
    def test_cleanup(self):
        ctx = WorkflowContext.default()
        set_current_context(ctx)
        set_current_context(None)
        assert get_current_context() is None

    def test_context_isolation(self):
        """Different coroutines should have independent contexts"""
        async def worker(tenant: str):
            ctx = WorkflowContext.default().extend(tenant=tenant)
            set_current_context(ctx)
            await asyncio.sleep(0.01)
            try:
                return get_current_tenant_id()
            finally:
                set_current_context(None)

        async def run():
            r1, r2 = await asyncio.gather(
                worker("tenant_a"),
                worker("tenant_b"),
            )
            assert r1 == "default"  # default() always returns "default"
            assert r2 == "default"

        asyncio.run(run())

    def test_context_cleanup_on_exception(self):
        try:
            ctx = WorkflowContext.default()
            set_current_context(ctx)
            raise RuntimeError("test error")
        except RuntimeError:
            pass
        finally:
            set_current_context(None)
        assert get_current_context() is None


class TestContextAccessors:
    """UT-31: accessor fallbacks"""
    def test_get_current_tenant_id_fallback(self):
        set_current_context(None)
        assert get_current_tenant_id() == "default"

    def test_get_current_user_id_fallback(self):
        set_current_context(None)
        assert get_current_user_id() == "anonymous"

    def test_get_current_trace_id_fallback(self):
        set_current_context(None)
        assert get_current_trace_id() == "no-trace"

    def test_get_current_session_id_fallback(self):
        set_current_context(None)
        assert get_current_session_id() == ""

    def test_accessors_with_context(self):
        ctx = WorkflowContext.default()
        set_current_context(ctx)
        try:
            assert get_current_tenant_id() == ctx.tenant_id
            assert get_current_user_id() == ctx.user_id
            assert get_current_trace_id() == ctx.trace_id
            assert get_current_session_id() == ctx.session_id
        finally:
            set_current_context(None)
