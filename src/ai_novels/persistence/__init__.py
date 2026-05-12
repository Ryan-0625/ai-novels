"""
持久化层模块

@file: persistence/__init__.py
@date: 2026-03-20
@version: 1.0
@description: 统一的数据持久化接口，封装Neo4j、MongoDB、ChromaDB操作
"""

from .manager import PersistenceManager, get_persistence_manager
from .agent_persist import (
    CharacterPersistence,
    WorldPersistence,
    OutlinePersistence,
    ChapterPersistence,
    QualityReportPersistence
)

__all__ = [
    'PersistenceManager',
    'get_persistence_manager',
    'CharacterPersistence',
    'WorldPersistence',
    'OutlinePersistence',
    'ChapterPersistence',
    'QualityReportPersistence',
]
