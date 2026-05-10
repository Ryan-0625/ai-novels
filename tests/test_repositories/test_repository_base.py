"""
Repository 模式单元测试

测试范围:
- BaseRepository CRUD 操作
- NovelRepository 扩展查询
- CharacterRepository 扩展查询
- TaskRepository 扩展查询

使用 mock AsyncSession 避免数据库依赖。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Character, ChapterContent, ChapterOutline, Novel, Task
from deepnovel.repositories import (
    BaseRepository,
    CharacterRepository,
    ChapterContentRepository,
    ChapterOutlineRepository,
    NovelRepository,
    TaskRepository,
    WorldEntityRepository,
)


class TestBaseRepository:
    """BaseRepository 通用测试"""

    @pytest.fixture
    def mock_session(self):
        """创建 mock AsyncSession"""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def novel_repo(self):
        return NovelRepository()

    def test_init(self):
        """Repository 初始化必须正确设置模型类"""
        repo = NovelRepository()
        assert repo._model == Novel

    @pytest.mark.asyncio
    async def test_get_by_id(self, mock_session, novel_repo):
        """get_by_id 必须调用正确的查询"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await novel_repo.get_by_id(mock_session, "novel-123")

        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all(self, mock_session, novel_repo):
        """get_all 必须返回列表"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await novel_repo.get_all(mock_session)

        assert result == []

    @pytest.mark.asyncio
    async def test_create(self, mock_session, novel_repo):
        """create 必须添加实体并刷新"""
        novel = Novel(title="Test Novel")

        result = await novel_repo.create(mock_session, novel)

        mock_session.add.assert_called_once_with(novel)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert result == novel

    @pytest.mark.asyncio
    async def test_update(self, mock_session, novel_repo):
        """update 必须添加并刷新实体"""
        novel = Novel(title="Updated")

        result = await novel_repo.update(mock_session, novel)

        mock_session.add.assert_called_once_with(novel)
        mock_session.flush.assert_awaited_once()
        assert result == novel

    @pytest.mark.asyncio
    async def test_delete_by_id_found(self, mock_session, novel_repo):
        """delete_by_id 找到实体时必须返回 True"""
        novel = Novel(title="To Delete")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = novel
        mock_session.execute.return_value = mock_result

        result = await novel_repo.delete_by_id(mock_session, "novel-123")

        assert result is True
        mock_session.delete.assert_awaited_once_with(novel)

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self, mock_session, novel_repo):
        """delete_by_id 未找到实体时必须返回 False"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await novel_repo.delete_by_id(mock_session, "not-exist")

        assert result is False

    @pytest.mark.asyncio
    async def test_count(self, mock_session, novel_repo):
        """count 必须返回整数"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        result = await novel_repo.count(mock_session)

        assert result == 42

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_session, novel_repo):
        """exists 实体存在时必须返回 True"""
        novel = Novel(title="Exists")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = novel
        mock_session.execute.return_value = mock_result

        result = await novel_repo.exists(mock_session, "novel-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, mock_session, novel_repo):
        """exists 实体不存在时必须返回 False"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await novel_repo.exists(mock_session, "not-exist")

        assert result is False


class TestNovelRepository:
    """NovelRepository 扩展方法测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self):
        return NovelRepository()

    @pytest.mark.asyncio
    async def test_get_by_title(self, mock_session, repo):
        """按标题查询必须正确调用"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_title(mock_session, "Test Title")

        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_status(self, mock_session, repo):
        """按状态查询必须返回列表"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_status(mock_session, "draft")

        assert result == []


class TestCharacterRepository:
    """CharacterRepository 扩展方法测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self):
        return CharacterRepository()

    @pytest.mark.asyncio
    async def test_get_by_novel(self, mock_session, repo):
        """按小说查询角色必须返回列表"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_novel(mock_session, "novel-123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_name(self, mock_session, repo):
        """按名称查询角色必须正确调用"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_name(mock_session, "novel-123", "Alice")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_archetype(self, mock_session, repo):
        """按原型查询角色必须返回列表"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_archetype(mock_session, "novel-123", "hero")

        assert result == []


class TestChapterRepositories:
    """Chapter Outline / Content Repository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_outline_get_by_novel(self, mock_session):
        """按小说查询章节大纲"""
        repo = ChapterOutlineRepository()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_novel(mock_session, "novel-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_outline_get_by_chapter_number(self, mock_session):
        """按章节号查询大纲"""
        repo = ChapterOutlineRepository()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_chapter_number(mock_session, "novel-123", 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_content_get_by_status(self, mock_session):
        """按状态查询章节正文"""
        repo = ChapterContentRepository()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_status(mock_session, "novel-123", "draft")
        assert result == []


class TestTaskRepository:
    """TaskRepository 扩展方法测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repo(self):
        return TaskRepository()

    @pytest.mark.asyncio
    async def test_get_by_status(self, mock_session, repo):
        """按状态查询任务"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_status(mock_session, "pending")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_type(self, mock_session, repo):
        """按类型查询任务"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_type(mock_session, "generation")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_active(self, mock_session, repo):
        """查询活跃任务"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_active(mock_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_novel(self, mock_session, repo):
        """按小说ID查询任务"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_novel(mock_session, "novel-123")
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
