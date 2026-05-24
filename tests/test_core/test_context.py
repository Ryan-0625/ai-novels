"""
Tests: WorkflowContext construction, default factory, JWT payload
"""

from datetime import datetime, timezone
from ai_novels.core.context import (
    WorkflowContext, TenantIdentity, UserIdentity,
    IdentityContext, ExecutionContext, MemoryScope,
    TenantTier, get_current_tenant_id, set_current_context,
)


class TestWorkflowContext:
    def test_default_factory(self):
        ctx = WorkflowContext.default()
        assert ctx.tenant_id == "default"
        assert ctx.user_id == "local"
        assert ctx.trace_id != ""
        assert ctx.session_id != ""
        assert ctx.execution.timeout_seconds == 60

    def test_from_jwt_payload(self):
        payload = {
            "sub": "u_001",
            "tenant_id": "t_pro",
            "tenant_name": "Pro Publisher",
            "tier": "pro",
            "features": ["advanced_outline", "unlimited_chapters"],
            "name": "Alice",
            "email": "alice@pub.com",
            "roles": ["editor", "admin"],
        }
        ctx = WorkflowContext.from_jwt_payload(payload)

        assert ctx.tenant_id == "t_pro"
        assert ctx.identity.tenant.tenant_name == "Pro Publisher"
        assert ctx.identity.tenant.tier == TenantTier.PRO
        assert ctx.identity.tenant.has_feature("advanced_outline") is True
        assert ctx.identity.tenant.has_feature("nonexistent") is False
        assert ctx.user_id == "u_001"
        assert ctx.identity.user.username == "Alice"
        assert "admin" in ctx.identity.user.roles

    def test_extend(self):
        ctx = WorkflowContext.default()
        ctx2 = ctx.extend(custom_key="custom_value")
        assert ctx2.extra["custom_key"] == "custom_value"
        # Original unchanged
        assert "custom_key" not in ctx.extra

    def test_immutable(self):
        ctx = WorkflowContext.default()
        import dataclasses
        assert dataclasses.frozen(ctx.__class__) is True

    def test_contextvars_bridge(self):
        ctx = WorkflowContext.default()
        set_current_context(ctx)
        try:
            tid = get_current_tenant_id()
            assert tid == "default"
        finally:
            set_current_context(None)
        # After cleanup, fallback to "default"
        assert get_current_tenant_id() == "default"

    def test_tenant_tier_enum(self):
        assert TenantTier.FREE.value == "free"
        assert TenantTier.PRO.value == "pro"
        assert TenantTier.ENTERPRISE.value == "enterprise"
