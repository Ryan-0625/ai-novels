"""
统一上下文内核 — WorkflowContext

职责: 作为全系统唯一的执行上下文契约, 承载身份/执行/记忆三维度。
定位: Data Object, 不可变 frozen=True, 线程安全。
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from datetime import datetime
import contextvars
import uuid


# ──────────────────────────────
# 身份维度
# ──────────────────────────────

class TenantTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class TenantIdentity:
    tenant_id: str
    tenant_name: str = "默认租户"
    tier: TenantTier = TenantTier.FREE
    features: Set[str] = field(default_factory=set)

    def has_feature(self, feature: str) -> bool:
        return feature in self.features


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    username: str = "anonymous"
    email: str = ""
    roles: Set[str] = field(default_factory=lambda: {"viewer"})


@dataclass(frozen=True)
class IdentityContext:
    tenant: TenantIdentity
    user: UserIdentity


# ──────────────────────────────
# 执行维度
# ──────────────────────────────

@dataclass(frozen=True)
class ExecutionContext:
    trace_id: str
    correlation_id: str = ""
    parent_trace_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 60


# ──────────────────────────────
# 记忆维度
# ──────────────────────────────

class MemoryType(str, Enum):
    WORKING = "working"
    SHORT_TERM = "short"
    LONG_TERM = "long"


@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    session_id: str
    agent_name: str
    task_id: Optional[str] = None
    tags: Set[str] = field(default_factory=set)


# ──────────────────────────────
# 聚合根
# ──────────────────────────────

@dataclass(frozen=True)
class WorkflowContext:
    identity: IdentityContext
    execution: ExecutionContext
    memory: MemoryScope
    created_at: datetime = field(default_factory=datetime.utcnow)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def tenant_id(self) -> str:
        return self.identity.tenant.tenant_id

    @property
    def user_id(self) -> str:
        return self.identity.user.user_id

    @property
    def trace_id(self) -> str:
        return self.execution.trace_id

    @property
    def session_id(self) -> str:
        return self.memory.session_id

    def extend(self, **kwargs) -> "WorkflowContext":
        return replace(self, extra={**self.extra, **kwargs})

    @classmethod
    def default(cls) -> "WorkflowContext":
        sid = str(uuid.uuid4())
        return cls(
            identity=IdentityContext(
                tenant=TenantIdentity(tenant_id="default"),
                user=UserIdentity(user_id="local"),
            ),
            execution=ExecutionContext(trace_id=str(uuid.uuid4())),
            memory=MemoryScope(tenant_id="default", session_id=sid, agent_name="system"),
        )

    @classmethod
    def from_jwt_payload(cls, payload: dict) -> "WorkflowContext":
        tid = payload.get("tenant_id", "default")
        sid = payload.get("session_id", str(uuid.uuid4()))
        return cls(
            identity=IdentityContext(
                tenant=TenantIdentity(
                    tenant_id=tid,
                    tenant_name=payload.get("tenant_name", ""),
                    tier=TenantTier(payload.get("tier", "free")),
                    features=set(payload.get("features", [])),
                ),
                user=UserIdentity(
                    user_id=payload.get("sub", "anonymous"),
                    username=payload.get("name", "anonymous"),
                    email=payload.get("email", ""),
                    roles=set(payload.get("roles", ["viewer"])),
                ),
            ),
            execution=ExecutionContext(
                trace_id=payload.get("trace_id", str(uuid.uuid4())),
                correlation_id=payload.get("correlation_id", ""),
            ),
            memory=MemoryScope(
                tenant_id=tid,
                session_id=sid,
                agent_name=payload.get("agent_name", "api"),
                task_id=payload.get("task_id"),
            ),
        )


# ──────────────────────────────
# contextvars 桥接 (向后兼容)
# ──────────────────────────────

_context_var: contextvars.ContextVar[Optional[WorkflowContext]] = (
    contextvars.ContextVar("workflow_context", default=None)
)


def set_current_context(ctx: Optional[WorkflowContext]) -> None:
    _context_var.set(ctx)


def get_current_context() -> Optional[WorkflowContext]:
    return _context_var.get()


def get_current_tenant_id() -> str:
    ctx = get_current_context()
    return ctx.tenant_id if ctx else "default"


def get_current_user_id() -> str:
    ctx = get_current_context()
    return ctx.user_id if ctx else "anonymous"


def get_current_trace_id() -> str:
    ctx = get_current_context()
    return ctx.trace_id if ctx else "no-trace"


def get_current_session_id() -> str:
    ctx = get_current_context()
    return ctx.session_id if ctx else ""
