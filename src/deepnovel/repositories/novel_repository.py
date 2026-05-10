"""
Novel / Character / WorldEntity Repository

@file: repositories/novel_repository.py
@date: 2026-04-29
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Character, Novel, WorldEntity

from .base import BaseRepository


class NovelRepository(BaseRepository[Novel]):
    """小说 Repository"""

    def __init__(self):
        super().__init__(Novel)

    async def get_by_title(self, session: AsyncSession, title: str) -> Optional[Novel]:
        """根据标题查找小说"""
        stmt = select(Novel).where(Novel.title == title)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        session: AsyncSession,
        status: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Novel]:
        """按状态分页获取小说"""
        stmt = select(Novel).where(Novel.status == status).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(
        self,
        session: AsyncSession,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Novel]:
        """按用户ID获取小说列表"""
        stmt = (
            select(Novel)
            .where(Novel.meta_info["user_id"].as_string() == user_id)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


class CharacterRepository(BaseRepository[Character]):
    """角色 Repository"""

    def __init__(self):
        super().__init__(Character)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Character]:
        """获取指定小说中的所有角色"""
        stmt = (
            select(Character)
            .where(Character.novel_id == novel_id)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(
        self,
        session: AsyncSession,
        novel_id: str,
        name: str,
    ) -> Optional[Character]:
        """根据名称获取角色（在指定小说内）"""
        stmt = (
            select(Character)
            .where(Character.novel_id == novel_id)
            .where(Character.name == name)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_archetype(
        self,
        session: AsyncSession,
        novel_id: str,
        archetype: str,
    ) -> List[Character]:
        """按原型获取角色"""
        stmt = (
            select(Character)
            .where(Character.novel_id == novel_id)
            .where(Character.archetype == archetype)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


class WorldEntityRepository(BaseRepository[WorldEntity]):
    """世界实体 Repository"""

    def __init__(self):
        super().__init__(WorldEntity)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[WorldEntity]:
        """获取指定小说中的世界实体"""
        stmt = (
            select(WorldEntity)
            .where(WorldEntity.novel_id == novel_id)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(
        self,
        session: AsyncSession,
        novel_id: str,
        category: str,
    ) -> List[WorldEntity]:
        """按类别获取世界实体"""
        stmt = (
            select(WorldEntity)
            .where(WorldEntity.novel_id == novel_id)
            .where(WorldEntity.category == category)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
