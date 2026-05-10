"""
Repository 模式 — 数据访问层

提供类型安全的异步数据访问，隔离业务逻辑与数据库操作。
所有 Repository 通过 SQLModel + asyncpg 与 PostgreSQL 交互。

@file: repositories/__init__.py
@date: 2026-04-29
"""

from .base import BaseRepository
from .chapter_repository import ChapterContentRepository, ChapterOutlineRepository
from .novel_repository import CharacterRepository, NovelRepository, WorldEntityRepository
from .task_repository import TaskRepository
from .world_simulation_repository import (
    FactRepository,
    EventRepository,
    NarrativeRepository,
    WorldRuleRepository,
)
from .memory_repository import (
    EpisodicMemoryRepository,
    SemanticMemoryRepository,
    EmotionalMemoryRepository,
    ProceduralMemoryRepository,
)

__all__ = [
    "BaseRepository",
    "NovelRepository",
    "CharacterRepository",
    "WorldEntityRepository",
    "ChapterOutlineRepository",
    "ChapterContentRepository",
    "TaskRepository",
    # 世界模拟 Repository
    "FactRepository",
    "EventRepository",
    "NarrativeRepository",
    "WorldRuleRepository",
    # 记忆系统 Repository
    "EpisodicMemoryRepository",
    "SemanticMemoryRepository",
    "EmotionalMemoryRepository",
    "ProceduralMemoryRepository",
]
