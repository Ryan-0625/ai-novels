"""
NovelService 单元测试

使用 mock AsyncSession 和 mock Repository 测试业务逻辑。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.models import Novel
from deepnovel.repositories import NovelRepository
from deepnovel.services import NovelService


class TestNovelService:
    """NovelService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=NovelRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return NovelService(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_create_novel(self, mock_session, mock_repo, service):
        """create_novel 必须创建并返回小说"""
        mock_repo.create.return_value = Novel(title="Test Novel")

        result = await service.create_novel(
            mock_session,
            title="Test Novel",
            genre="sci-fi",
        )

        assert result.title == "Test Novel"
        mock_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_novel_found(self, mock_session, mock_repo, service):
        """get_novel 找到小说时必须返回"""
        novel = Novel(title="Found")
        mock_repo.get_by_id.return_value = novel

        result = await service.get_novel(mock_session, "novel-123")

        assert result == novel
        mock_repo.get_by_id.assert_awaited_once_with(mock_session, "novel-123")

    @pytest.mark.asyncio
    async def test_get_novel_not_found(self, mock_session, mock_repo, service):
        """get_novel 未找到时必须返回 None"""
        mock_repo.get_by_id.return_value = None

        result = await service.get_novel(mock_session, "not-exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_novels_by_status(self, mock_session, mock_repo, service):
        """list_novels 按状态过滤时必须调用正确的 repo 方法"""
        mock_repo.get_by_status.return_value = []

        result = await service.list_novels(mock_session, status="draft")

        assert result == []
        mock_repo.get_by_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_novel_status(self, mock_session, mock_repo, service):
        """update_novel_status 必须更新状态"""
        novel = Novel(title="Test", status="draft")
        mock_repo.get_by_id.return_value = novel
        mock_repo.update.return_value = novel

        result = await service.update_novel_status(mock_session, "novel-123", "writing")

        assert result.status == "writing"
        mock_repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_novel_status_not_found(self, mock_session, mock_repo, service):
        """update_novel_status 未找到时必须返回 None"""
        mock_repo.get_by_id.return_value = None

        result = await service.update_novel_status(mock_session, "not-exist", "writing")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_novel(self, mock_session, mock_repo, service):
        """delete_novel 必须返回删除结果"""
        mock_repo.delete_by_id.return_value = True

        result = await service.delete_novel(mock_session, "novel-123")

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
