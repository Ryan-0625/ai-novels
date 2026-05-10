"""
Task Repository

@file: repositories/task_repository.py
@date: 2026-04-29
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Task

from .base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """任务 Repository"""

    def __init__(self):
        super().__init__(Task)

    async def get_by_status(
        self,
        session: AsyncSession,
        status: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """按状态获取任务"""
        stmt = (
            select(Task)
            .where(Task.status == status)
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(
        self,
        session: AsyncSession,
        task_type: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """按类型获取任务"""
        stmt = (
            select(Task)
            .where(Task.task_type == task_type)
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """按小说ID获取任务"""
        stmt = (
            select(Task)
            .where(Task.novel_id == novel_id)
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_active(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """获取活跃任务（非终态）"""
        from deepnovel.models.task import TaskStatus

        terminal = {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED}
        stmt = (
            select(Task)
            .where(Task.status.notin_(terminal))
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
