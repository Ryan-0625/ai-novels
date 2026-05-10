"""
Chapter Repository

@file: repositories/chapter_repository.py
@date: 2026-04-29
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import ChapterContent, ChapterOutline

from .base import BaseRepository


class ChapterOutlineRepository(BaseRepository[ChapterOutline]):
    """章节大纲 Repository"""

    def __init__(self):
        super().__init__(ChapterOutline)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[ChapterOutline]:
        """按小说获取章节大纲"""
        stmt = (
            select(ChapterOutline)
            .where(ChapterOutline.novel_id == novel_id)
            .order_by(ChapterOutline.chapter_number)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_chapter_number(
        self,
        session: AsyncSession,
        novel_id: str,
        chapter_number: int,
    ) -> Optional[ChapterOutline]:
        """按章节号获取大纲"""
        stmt = (
            select(ChapterOutline)
            .where(ChapterOutline.novel_id == novel_id)
            .where(ChapterOutline.chapter_number == chapter_number)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


class ChapterContentRepository(BaseRepository[ChapterContent]):
    """章节正文 Repository"""

    def __init__(self):
        super().__init__(ChapterContent)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[ChapterContent]:
        """按小说获取章节正文"""
        stmt = (
            select(ChapterContent)
            .where(ChapterContent.novel_id == novel_id)
            .order_by(ChapterContent.chapter_number)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(
        self,
        session: AsyncSession,
        novel_id: str,
        status: str,
    ) -> List[ChapterContent]:
        """按状态获取章节正文"""
        stmt = (
            select(ChapterContent)
            .where(ChapterContent.novel_id == novel_id)
            .where(ChapterContent.status == status)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
