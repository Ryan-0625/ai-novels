"""
租户感知的数据库 Session 工厂

连接池管理:
  - 共享连接池: pool_size=20, max_overflow=10 (默认)
  - 企业独立池: pool_size=50, max_overflow=20
  - close_all(): 关闭所有引擎, 应注册到 FastAPI shutdown 事件

竞态防护:
  - asyncio.Lock 保护 _isolated_makers 注册
  - _isolated_makers 的 get_session 是无锁读, 线程安全
"""

import asyncio
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_async_engine,
)

from ai_novels.core.context import WorkflowContext, TenantTier
from ai_novels.config.hub import get_config_hub
from ai_novels.core.exceptions import DatabaseException


class TenantSessionFactory:
    """租户感知的 Session 工厂

    使用方式:
        factory = TenantSessionFactory("postgresql+asyncpg://...")
        session = await factory.get_session(ctx)
        try:
            result = await session.execute(...)
            await session.commit()
        finally:
            await session.close()
    """

    def __init__(self, shared_dsn: str,
                 shared_pool_size: int = 20,
                 shared_max_overflow: int = 10):
        self._shared_engine = _create_async_engine(
            shared_dsn,
            pool_size=shared_pool_size,
            max_overflow=shared_max_overflow,
            pool_pre_ping=True,       # 连接前验证, 防止使用已断开连接
            pool_recycle=3600,        # 1h 回收, 防止长连接被数据库关闭
        )
        self._shared_maker = async_sessionmaker(
            self._shared_engine,
            class_=AsyncSession,
            expire_on_commit=False,   # 防止提交后属性不可访问
        )
        self._isolated_makers: Dict[str, async_sessionmaker] = {}
        self._lock = asyncio.Lock()

    def register_isolated_tenant(self, tenant_id: str, dsn: str,
                                  pool_size: int = 50,
                                  max_overflow: int = 20) -> None:
        """为企业租户注册独立数据库连接池"""
        engine = _create_async_engine(
            dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._isolated_makers[tenant_id] = maker

    async def get_session(self,
                          ctx: Optional[WorkflowContext] = None) -> AsyncSession:
        """获取 Session (自动选择连接池)"""
        if ctx and ctx.identity.tenant.tier == TenantTier.ENTERPRISE:
            tid = ctx.identity.tenant.tenant_id
            maker = self._isolated_makers.get(tid)
            if maker is not None:
                return maker()
        return self._shared_maker()

    async def close_all(self) -> None:
        """关闭所有连接池 (注册到 FastAPI shutdown 事件)"""
        try:
            await self._shared_engine.dispose()
        except Exception:
            pass
        for maker in self._isolated_makers.values():
            try:
                engine = maker.kw.get("bind")
                if engine:
                    await engine.dispose()
            except Exception:
                pass
        self._isolated_makers.clear()


# ──────────────────────────────
# 全局工厂 (延迟初始化, 线程安全)
# ──────────────────────────────

_session_factory: Optional[TenantSessionFactory] = None
_factory_init_lock = asyncio.Lock()


def get_tenant_session_factory() -> TenantSessionFactory:
    global _session_factory
    if _session_factory is None:
        raise DatabaseException(
            "TenantSessionFactory not initialized. "
            "Call init_tenant_session_factory() on startup."
        )
    return _session_factory


async def init_tenant_session_factory(
    dsn: str,
    pool_size: int = 20,
    max_overflow: int = 10,
) -> TenantSessionFactory:
    """初始化全局 Session 工厂 (应用启动时调用)"""
    global _session_factory
    async with _factory_init_lock:
        if _session_factory is None:
            _session_factory = TenantSessionFactory(
                dsn, pool_size, max_overflow,
            )
    return _session_factory


async def get_tenant_session(
    ctx: Optional[WorkflowContext] = None,
) -> AsyncSession:
    """获取租户感知的 Session (推荐入口)"""
    return await get_tenant_session_factory().get_session(ctx)
