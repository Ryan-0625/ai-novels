"""
Repository 基类

提供通用的异步 CRUD 操作，所有具体 Repository 继承此类。

@file: repositories/base.py
@date: 2026-04-29
"""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

ModelT = TypeVar("ModelT", bound=SQLModel)


class BaseRepository(Generic[ModelT]):
    """通用异步 Repository 基类

    封装标准 CRUD 操作，支持类型安全的数据访问。
    所有方法接受 AsyncSession，由调用方控制事务边界。
    """

    def __init__(self, model_class: Type[ModelT]):
        self._model = model_class

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> Optional[ModelT]:
        """根据ID获取实体"""
        stmt = select(self._model).where(self._model.id == entity_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[ModelT]:
        """分页获取所有实体"""
        stmt = select(self._model).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, entity: ModelT) -> ModelT:
        """创建实体"""
        session.add(entity)
        await session.flush()
        await session.refresh(entity)
        return entity

    async def update(self, session: AsyncSession, entity: ModelT) -> ModelT:
        """更新实体（实体必须已附加到session）"""
        session.add(entity)
        await session.flush()
        await session.refresh(entity)
        return entity

    async def delete(self, session: AsyncSession, entity: ModelT) -> None:
        """删除实体"""
        await session.delete(entity)
        await session.flush()

    async def delete_by_id(self, session: AsyncSession, entity_id: str) -> bool:
        """根据ID删除实体，返回是否成功"""
        entity = await self.get_by_id(session, entity_id)
        if entity is None:
            return False
        await self.delete(session, entity)
        return True

    async def count(self, session: AsyncSession) -> int:
        """获取实体总数"""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self._model)
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def exists(self, session: AsyncSession, entity_id: str) -> bool:
        """检查实体是否存在"""
        entity = await self.get_by_id(session, entity_id)
        return entity is not None
