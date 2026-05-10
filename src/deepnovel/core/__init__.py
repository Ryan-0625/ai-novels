"""
核心模块初始化

@file: core/__init__.py
@date: 2026-04-29
@author: AI-Novels Team
@version: 2.0
@description: 核心功能模块初始化
"""

from .event_bus import EventBus, EventType, EventPriority
from .memory_context import MemoryContext
from .performance_monitor import PerformanceMonitor, get_performance_monitor
from .working_memory import (
    AttentionController,
    CharacterMindController,
    WorkingMemory,
    WorkingMemoryEntry,
)

# 保留旧版导出（向后兼容）
from .llm_router import LLMRouter, LLMProvider, LLMConfig

__all__ = [
    # v2.0 新增核心
    'EventBus',
    'EventType',
    'EventPriority',
    'MemoryContext',
    'PerformanceMonitor',
    'get_performance_monitor',
    'AttentionController',
    'CharacterMindController',
    'WorkingMemory',
    'WorkingMemoryEntry',
    # 旧版兼容
    'LLMRouter',
    'LLMProvider',
    'LLMConfig',
]
