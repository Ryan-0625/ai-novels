"""
服务层 — 业务逻辑封装

@file: services/__init__.py
@date: 2026-04-29
"""

from .base import BaseService
from .health_service import get_health_service, HealthService
from .novel_service import NovelService
from .task_service import TaskService
from .world_state_service import WorldStateService
from .event_service import EventService
from .narrative_service import NarrativeService
from .world_rule_service import WorldRuleService
from .memory_service import (
    MemoryEncodingService,
    MemoryRetrievalService,
    MemoryConsolidationService,
    MemoryForgettingService,
    MemoryManager,
)

__all__ = [
    "BaseService",
    "get_health_service",
    "HealthService",
    "NovelService",
    "TaskService",
    # 世界模拟服务
    "WorldStateService",
    "EventService",
    "NarrativeService",
    "WorldRuleService",
    # 记忆系统服务
    "MemoryEncodingService",
    "MemoryRetrievalService",
    "MemoryConsolidationService",
    "MemoryForgettingService",
    "MemoryManager",
]
