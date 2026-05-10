"""
小说服务层

封装小说相关的业务逻辑。

@file: services/novel_service.py
@date: 2026-04-29
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Novel
from deepnovel.repositories import NovelRepository

from .base import BaseService


class NovelService(BaseService[NovelRepository]):
    """小说服务"""

    def __init__(self, repository: Optional[NovelRepository] = None):
        super().__init__(repository or NovelRepository())

    async def create_novel(
        self,
        session: AsyncSession,
        *,
        title: str,
        genre: str = "",
        tone: str = "",
        target_audience: str = "",
        synopsis: str = "",
        word_count_target: int = 50000,
    ) -> Novel:
        """创建小说"""
        novel = Novel(
            title=title,
            genre=genre,
            tone=tone,
            target_audience=target_audience,
            synopsis=synopsis,
            word_count_target=word_count_target,
        )
        return await self._repo.create(session, novel)

    async def get_novel(self, session: AsyncSession, novel_id: str) -> Optional[Novel]:
        """获取小说"""
        return await self._repo.get_by_id(session, novel_id)

    async def list_novels(
        self,
        session: AsyncSession,
        *,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Novel]:
        """列出小说"""
        if status:
            return await self._repo.get_by_status(session, status, offset=offset, limit=limit)
        return await self._repo.get_all(session, offset=offset, limit=limit)

    async def update_novel_status(
        self,
        session: AsyncSession,
        novel_id: str,
        status: str,
    ) -> Optional[Novel]:
        """更新小说状态"""
        novel = await self._repo.get_by_id(session, novel_id)
        if novel is None:
            return None
        novel.status = status
        return await self._repo.update(session, novel)

    async def delete_novel(self, session: AsyncSession, novel_id: str) -> bool:
        """删除小说"""
        return await self._repo.delete_by_id(session, novel_id)
