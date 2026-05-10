"""
任务服务层

封装任务相关的业务逻辑。

@file: services/task_service.py
@date: 2026-04-29
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Task
from deepnovel.models.task import TaskStatus
from deepnovel.repositories import TaskRepository

from .base import BaseService


class TaskService(BaseService[TaskRepository]):
    """任务服务"""

    def __init__(self, repository: Optional[TaskRepository] = None):
        super().__init__(repository or TaskRepository())

    async def create_task(
        self,
        session: AsyncSession,
        *,
        name: str,
        task_type: str,
        novel_id: Optional[str] = None,
        config: dict = None,
    ) -> Task:
        """创建任务"""
        task = Task(
            name=name,
            task_type=task_type,
            novel_id=novel_id,
            status=TaskStatus.PENDING,
            config=config or {},
        )
        return await self._repo.create(session, task)

    async def get_task(self, session: AsyncSession, task_id: str) -> Optional[Task]:
        """获取任务"""
        return await self._repo.get_by_id(session, task_id)

    async def list_tasks(
        self,
        session: AsyncSession,
        *,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """列出任务"""
        if status:
            return await self._repo.get_by_status(session, status, offset=offset, limit=limit)
        if task_type:
            return await self._repo.get_by_type(session, task_type, offset=offset, limit=limit)
        return await self._repo.get_all(session, offset=offset, limit=limit)

    async def start_task(self, session: AsyncSession, task_id: str) -> Optional[Task]:
        """启动任务"""
        task = await self._repo.get_by_id(session, task_id)
        if task is None:
            return None
        if task.status != TaskStatus.PENDING:
            return None
        task.status = TaskStatus.RUNNING
        return await self._repo.update(session, task)

    async def complete_task(
        self,
        session: AsyncSession,
        task_id: str,
        result: dict = None,
    ) -> Optional[Task]:
        """完成任务"""
        task = await self._repo.get_by_id(session, task_id)
        if task is None:
            return None
        task.status = TaskStatus.COMPLETED
        if result:
            task.result = result
        return await self._repo.update(session, task)

    async def fail_task(
        self,
        session: AsyncSession,
        task_id: str,
        error: str,
    ) -> Optional[Task]:
        """标记任务失败"""
        task = await self._repo.get_by_id(session, task_id)
        if task is None:
            return None
        task.status = TaskStatus.FAILED
        task.error = error
        return await self._repo.update(session, task)

    async def list_active_tasks(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """列出活跃任务"""
        return await self._repo.get_active(session, offset=offset, limit=limit)
