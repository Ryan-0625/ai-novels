"""
FastAPI 依赖注入层单元测试

测试范围:
- RepositoryProvider 工厂方法
- get_config_dep 配置依赖
"""

import pytest

from deepnovel.api.dependencies import RepositoryProvider, get_config_dep
from deepnovel.repositories import (
    CharacterRepository,
    ChapterContentRepository,
    ChapterOutlineRepository,
    NovelRepository,
    TaskRepository,
    WorldEntityRepository,
)


class TestRepositoryProvider:
    """RepositoryProvider 工厂测试"""

    def test_get_novel_repo(self):
        """get_novel_repo 必须返回 NovelRepository"""
        repo = RepositoryProvider.get_novel_repo()
        assert isinstance(repo, NovelRepository)

    def test_get_character_repo(self):
        """get_character_repo 必须返回 CharacterRepository"""
        repo = RepositoryProvider.get_character_repo()
        assert isinstance(repo, CharacterRepository)

    def test_get_world_entity_repo(self):
        """get_world_entity_repo 必须返回 WorldEntityRepository"""
        repo = RepositoryProvider.get_world_entity_repo()
        assert isinstance(repo, WorldEntityRepository)

    def test_get_chapter_outline_repo(self):
        """get_chapter_outline_repo 必须返回 ChapterOutlineRepository"""
        repo = RepositoryProvider.get_chapter_outline_repo()
        assert isinstance(repo, ChapterOutlineRepository)

    def test_get_chapter_content_repo(self):
        """get_chapter_content_repo 必须返回 ChapterContentRepository"""
        repo = RepositoryProvider.get_chapter_content_repo()
        assert isinstance(repo, ChapterContentRepository)

    def test_get_task_repo(self):
        """get_task_repo 必须返回 TaskRepository"""
        repo = RepositoryProvider.get_task_repo()
        assert isinstance(repo, TaskRepository)

    def test_repositories_are_singleton_instances(self):
        """每次调用应返回新实例（避免状态共享）"""
        r1 = RepositoryProvider.get_novel_repo()
        r2 = RepositoryProvider.get_novel_repo()
        assert r1 is not r2


class TestConfigDependency:
    """配置依赖测试"""

    @pytest.mark.asyncio
    async def test_get_config_dep_returns_app_config(self):
        """get_config_dep 必须返回 AppConfig"""
        from deepnovel.config.app_config import AppConfig

        config = await get_config_dep()
        assert isinstance(config, AppConfig)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
