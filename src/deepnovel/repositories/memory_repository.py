"""
记忆系统 Repository — 四级长期记忆的数据访问层

@file: repositories/memory_repository.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import (
    EpisodicMemory,
    SemanticMemory,
    EmotionalMemory,
    ProceduralMemory,
)

from .base import BaseRepository


class EpisodicMemoryRepository(BaseRepository[EpisodicMemory]):
    """情节记忆 Repository — 支持情感和情境查询"""

    def __init__(self):
        super().__init__(EpisodicMemory)

    async def get_by_character(
        self,
        session: AsyncSession,
        character_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[EpisodicMemory]:
        """获取角色的所有情节记忆（按强度排序）"""
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.character_id == character_id)
            .order_by(desc(EpisodicMemory.strength))
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_emotion_range(
        self,
        session: AsyncSession,
        character_id: str,
        min_valence: float = -1.0,
        max_valence: float = 1.0,
        min_arousal: float = 0.0,
        max_arousal: float = 1.0,
        *,
        limit: int = 50,
    ) -> List[EpisodicMemory]:
        """按情感范围查询记忆"""
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.character_id == character_id)
            .where(EpisodicMemory.emotional_valence.between(min_valence, max_valence))
            .where(EpisodicMemory.emotional_arousal.between(min_arousal, max_arousal))
            .order_by(desc(EpisodicMemory.strength))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_context_tags(
        self,
        session: AsyncSession,
        character_id: str,
        tags: List[str],
    ) -> List[EpisodicMemory]:
        """按情境标签查询记忆"""
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.character_id == character_id)
            .where(or_(*[EpisodicMemory.context_tags.contains([tag]) for tag in tags]))
            .order_by(desc(EpisodicMemory.strength))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(
        self,
        session: AsyncSession,
        character_id: str,
        time_window_seconds: int = 86400,
    ) -> List[EpisodicMemory]:
        """获取最近经历的记忆"""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)
        stmt = (
            select(EpisodicMemory)
            .where(EpisodicMemory.character_id == character_id)
            .where(EpisodicMemory.experienced_at >= cutoff)
            .order_by(desc(EpisodicMemory.experienced_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def increment_access(
        self,
        session: AsyncSession,
        memory_id: str,
    ) -> Optional[EpisodicMemory]:
        """增加记忆访问计数"""
        memory = await self.get_by_id(session, memory_id)
        if not memory:
            return None
        memory.access_count += 1
        memory.last_accessed = datetime.now(timezone.utc)
        return await self.update(session, memory)


class SemanticMemoryRepository(BaseRepository[SemanticMemory]):
    """语义记忆 Repository — 知识管理"""

    def __init__(self):
        super().__init__(SemanticMemory)

    async def get_by_character(
        self,
        session: AsyncSession,
        character_id: str,
        knowledge_type: Optional[str] = None,
    ) -> List[SemanticMemory]:
        """获取角色的语义记忆"""
        stmt = select(SemanticMemory).where(SemanticMemory.character_id == character_id)
        if knowledge_type:
            stmt = stmt.where(SemanticMemory.knowledge_type == knowledge_type)
        stmt = stmt.order_by(desc(SemanticMemory.confidence))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_concept(
        self,
        session: AsyncSession,
        character_id: str,
        concept_key: str,
    ) -> Optional[SemanticMemory]:
        """按概念键查询知识"""
        stmt = (
            select(SemanticMemory)
            .where(SemanticMemory.character_id == character_id)
            .where(SemanticMemory.concept_key == concept_key)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_high_confidence(
        self,
        session: AsyncSession,
        character_id: str,
        min_confidence: float = 0.7,
    ) -> List[SemanticMemory]:
        """获取高置信度知识"""
        stmt = (
            select(SemanticMemory)
            .where(SemanticMemory.character_id == character_id)
            .where(SemanticMemory.confidence >= min_confidence)
            .order_by(desc(SemanticMemory.confidence))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def increment_access(
        self,
        session: AsyncSession,
        memory_id: str,
    ) -> Optional[SemanticMemory]:
        """增加知识访问计数"""
        memory = await self.get_by_id(session, memory_id)
        if not memory:
            return None
        memory.access_count += 1
        memory.last_accessed = datetime.now(timezone.utc)
        return await self.update(session, memory)


class EmotionalMemoryRepository(BaseRepository[EmotionalMemory]):
    """情感记忆 Repository — 条件化情感反应"""

    def __init__(self):
        super().__init__(EmotionalMemory)

    async def get_by_character(
        self,
        session: AsyncSession,
        character_id: str,
        trigger_type: Optional[str] = None,
    ) -> List[EmotionalMemory]:
        """获取角色的情感记忆"""
        stmt = select(EmotionalMemory).where(EmotionalMemory.character_id == character_id)
        if trigger_type:
            stmt = stmt.where(EmotionalMemory.trigger_type == trigger_type)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_trigger(
        self,
        session: AsyncSession,
        character_id: str,
        trigger_type: str,
        trigger_pattern: str,
    ) -> List[EmotionalMemory]:
        """按触发器查询情感记忆"""
        stmt = (
            select(EmotionalMemory)
            .where(EmotionalMemory.character_id == character_id)
            .where(EmotionalMemory.trigger_type == trigger_type)
            .where(EmotionalMemory.trigger_pattern.contains(trigger_pattern))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_emotion(
        self,
        session: AsyncSession,
        character_id: str,
        emotion: str,
    ) -> List[EmotionalMemory]:
        """按情感类型查询"""
        stmt = (
            select(EmotionalMemory)
            .where(EmotionalMemory.character_id == character_id)
            .where(EmotionalMemory.triggered_emotion == emotion)
            .order_by(desc(EmotionalMemory.conditioning_strength))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


class ProceduralMemoryRepository(BaseRepository[ProceduralMemory]):
    """程序记忆 Repository — 技能管理"""

    def __init__(self):
        super().__init__(ProceduralMemory)

    async def get_by_character(
        self,
        session: AsyncSession,
        character_id: str,
        category: Optional[str] = None,
    ) -> List[ProceduralMemory]:
        """获取角色的技能"""
        stmt = select(ProceduralMemory).where(ProceduralMemory.character_id == character_id)
        if category:
            stmt = stmt.where(ProceduralMemory.skill_category == category)
        stmt = stmt.order_by(desc(ProceduralMemory.proficiency))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_skill_name(
        self,
        session: AsyncSession,
        character_id: str,
        skill_name: str,
    ) -> Optional[ProceduralMemory]:
        """按技能名称查询"""
        stmt = (
            select(ProceduralMemory)
            .where(ProceduralMemory.character_id == character_id)
            .where(ProceduralMemory.skill_name == skill_name)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_automatic_skills(
        self,
        session: AsyncSession,
        character_id: str,
    ) -> List[ProceduralMemory]:
        """获取已自动化的技能"""
        stmt = (
            select(ProceduralMemory)
            .where(ProceduralMemory.character_id == character_id)
            .where(ProceduralMemory.is_automatic.is_(True))
            .order_by(desc(ProceduralMemory.proficiency))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
