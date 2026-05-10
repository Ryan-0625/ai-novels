"""
FastAPI 依赖注入层

提供标准的 FastAPI Depends 函数，连接基础设施与 API 层：
- 数据库会话注入
- 配置注入
- Repository 注入

@file: api/dependencies.py
@date: 2026-04-29
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.config.app_config import AppConfig, get_config
from deepnovel.config.hub import ConfigHub, get_config_hub
from deepnovel.database.engine import get_db
from deepnovel.repositories import (
    CharacterRepository,
    ChapterContentRepository,
    ChapterOutlineRepository,
    NovelRepository,
    TaskRepository,
    WorldEntityRepository,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 数据库会话依赖"""
    async for session in get_db():
        yield session


async def get_config_dep() -> AppConfig:
    """FastAPI 配置依赖（新版 - 通过 ConfigHub）"""
    return get_config_hub().config


async def get_config_hub_dep() -> ConfigHub:
    """FastAPI ConfigHub 依赖"""
    return get_config_hub()


class RepositoryProvider:
    """Repository 工厂 — 用于 FastAPI Depends"""

    @staticmethod
    def get_novel_repo() -> NovelRepository:
        return NovelRepository()

    @staticmethod
    def get_character_repo() -> CharacterRepository:
        return CharacterRepository()

    @staticmethod
    def get_world_entity_repo() -> WorldEntityRepository:
        return WorldEntityRepository()

    @staticmethod
    def get_chapter_outline_repo() -> ChapterOutlineRepository:
        return ChapterOutlineRepository()

    @staticmethod
    def get_chapter_content_repo() -> ChapterContentRepository:
        return ChapterContentRepository()

    @staticmethod
    def get_task_repo() -> TaskRepository:
        return TaskRepository()
