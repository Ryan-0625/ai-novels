"""
AI-Novels 数据模型定义

@file: src/ai_novels/model/__init__.py
@date: 2026-03-12
@version: 1.0.0
@description: 定义消息格式、实体模型和数据传输对象
"""

from ai_novels.message.message import (
    TaskRequest,
    TaskResponse,
    TaskStatusUpdate,
    AgentMessage,
)

from ai_novels.message.entities import (
    Character,
    WorldEntity,
    OutlineNode,
    ChapterOutline,
    Conflict,
    NarrativeHook,
)

__all__ = [
    # 消息格式
    "TaskRequest",
    "TaskResponse",
    "TaskStatusUpdate",
    "AgentMessage",
    # 实体模型
    "Character",
    "WorldEntity",
    "OutlineNode",
    "ChapterOutline",
    "Conflict",
    "NarrativeHook",
]
