"""
TaskService 单元测试

使用 mock AsyncSession 和 mock Repository 测试业务逻辑。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.models import Task
from deepnovel.models.task import TaskStatus
from deepnovel.repositories import TaskRepository
from deepnovel.services import TaskService


class TestTaskService:
    """TaskService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=TaskRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return TaskService(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_create_task(self, mock_session, mock_repo, service):
        """create_task 必须创建任务并设置默认状态"""
        mock_repo.create.return_value = Task(name="Generate Chapter", task_type="generation")

        result = await service.create_task(
            mock_session,
            name="Generate Chapter",
            task_type="generation",
        )

        assert result.name == "Generate Chapter"
        mock_repo.create.assert_awaited_once()
        # 验证状态为 pending
        created_task = mock_repo.create.call_args[0][1]
        assert created_task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_task_found(self, mock_session, mock_repo, service):
        """get_task 找到任务时必须返回"""
        task = Task(name="Found")
        mock_repo.get_by_id.return_value = task

        result = await service.get_task(mock_session, "task-123")

        assert result == task

    @pytest.mark.asyncio
    async def test_start_task(self, mock_session, mock_repo, service):
        """start_task 必须将 pending 任务改为 running"""
        task = Task(name="Test", status=TaskStatus.PENDING)
        mock_repo.get_by_id.return_value = task
        mock_repo.update.return_value = task

        result = await service.start_task(mock_session, "task-123")

        assert result.status == TaskStatus.RUNNING
        mock_repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_task_not_pending(self, mock_session, mock_repo, service):
        """start_task 非 pending 任务必须返回 None"""
        task = Task(name="Test", status=TaskStatus.RUNNING)
        mock_repo.get_by_id.return_value = task

        result = await service.start_task(mock_session, "task-123")

        assert result is None
        mock_repo.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_complete_task(self, mock_session, mock_repo, service):
        """complete_task 必须标记为 completed 并保存结果"""
        task = Task(name="Test", status=TaskStatus.RUNNING)
        mock_repo.get_by_id.return_value = task
        mock_repo.update.return_value = task

        result = await service.complete_task(mock_session, "task-123", result={"word_count": 3000})

        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"word_count": 3000}

    @pytest.mark.asyncio
    async def test_fail_task(self, mock_session, mock_repo, service):
        """fail_task 必须标记为 failed 并保存错误"""
        task = Task(name="Test")
        mock_repo.get_by_id.return_value = task
        mock_repo.update.return_value = task

        result = await service.fail_task(mock_session, "task-123", error="LLM timeout")

        assert result.status == TaskStatus.FAILED
        assert result.error == "LLM timeout"

    @pytest.mark.asyncio
    async def test_list_active_tasks(self, mock_session, mock_repo, service):
        """list_active_tasks 必须返回活跃任务"""
        mock_repo.get_active.return_value = []

        result = await service.list_active_tasks(mock_session)

        assert result == []
        mock_repo.get_active.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
