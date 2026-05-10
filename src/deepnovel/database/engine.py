"""
PostgreSQL 数据库引擎配置

使用 SQLModel (SQLAlchemy 2.0) + asyncpg 提供异步数据库访问。
配置从 AppConfig 统一配置中心读取。

@file: database/engine.py
@date: 2026-04-29
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from deepnovel.config.app_config import get_config

_engine = None
_async_session_maker = None


def _init_engine():
    """创建异步引擎（从AppConfig读取配置）"""
    global _engine, _async_session_maker
    if _engine is not None:
        return

    cfg = get_config()
    db = cfg.database

    url = db.url
    # 确保使用异步驱动
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    _engine = create_async_engine(
        url,
        echo=db.echo,
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_pre_ping=db.pool_pre_ping,
        pool_recycle=db.pool_recycle,
    )

    _async_session_maker = sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_engine():
    """获取异步引擎单例"""
    _init_engine()
    return _engine


def get_session_maker():
    """获取异步会话工厂"""
    _init_engine()
    return _async_session_maker


async def init_db():
    """初始化数据库 — 创建所有表"""
    # 延迟导入模型以确保表注册
    from deepnovel.models import novel, chapter, narrative, task  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    global _engine, _async_session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None


@asynccontextmanager
async def get_session():
    """获取数据库会话的上下文管理器"""
    maker = get_session_maker()
    session = maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db():
    """FastAPI依赖注入用的数据库会话生成器"""
    maker = get_session_maker()
    session = maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
